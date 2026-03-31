"""
Validador de XML VRSync para importacao na plataforma Mellro.

Este modulo contem toda a logica de validacao dos campos do XML
no formato VRSync (padrao Grupo OLX/VivaReal), que e o formato
aceito pela plataforma Mellro para importacao de imoveis.

Regras baseadas na documentacao oficial:
https://developers.grupozap.com/feeds/vrsync/elements/
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from xml.etree import ElementTree as ET


# ---------------------------------------------------------------------------
# Tipos e constantes
# ---------------------------------------------------------------------------

class Severidade(Enum):
    """Nivel de severidade de um problema encontrado no XML."""
    ERRO = "ERRO"       # Impede a importacao do imovel
    AVISO = "AVISO"     # Pode causar problemas, mas nao impede


@dataclass
class Problema:
    """Representa um problema encontrado durante a validacao."""
    severidade: Severidade
    campo: str
    mensagem: str
    imovel_id: Optional[str] = None


@dataclass
class ResultadoImovel:
    """Resultado da validacao de um unico imovel (Listing)."""
    imovel_id: Optional[str]
    problemas: list[Problema] = field(default_factory=list)

    @property
    def tem_erros(self) -> bool:
        return any(p.severidade == Severidade.ERRO for p in self.problemas)

    @property
    def tem_avisos(self) -> bool:
        return any(p.severidade == Severidade.AVISO for p in self.problemas)


@dataclass
class ResultadoValidacao:
    """Resultado completo da validacao de um arquivo XML."""
    problemas_gerais: list[Problema] = field(default_factory=list)
    imoveis: list[ResultadoImovel] = field(default_factory=list)
    total_imoveis: int = 0

    def __post_init__(self):
        self._cache_com_erro: Optional[int] = None
        self._cache_sem_problema: Optional[int] = None

    @property
    def imoveis_com_erro(self) -> int:
        if self._cache_com_erro is None:
            self._cache_com_erro = sum(1 for i in self.imoveis if i.tem_erros)
        return self._cache_com_erro

    @property
    def imoveis_sem_problema(self) -> int:
        if self._cache_sem_problema is None:
            self._cache_sem_problema = sum(
                1 for i in self.imoveis if not i.problemas
            )
        return self._cache_sem_problema


# Tipos de imovel validos no formato VRSync
TIPOS_IMOVEL_VALIDOS = {
    "Residential / Home",
    "Residential / Condo",
    "Residential / Village House",
    "Residential / Farm Ranch",
    "Residential / Penthouse",
    "Residential / Flat",
    "Residential / Kitnet",
    "Residential / Land Lot",
    "Residential / Studio",
    "Residential / Sobrado",
    "Residential / Agricultural",
    "Residential / Apartment",
}

# Tipos de transacao validos
TIPOS_TRANSACAO_VALIDOS = {"For Rent"}

# Tipos de publicacao validos
TIPOS_PUBLICACAO_VALIDOS = {
    "STANDARD", "PREMIUM", "SUPER_PREMIUM",
    "PREMIERE_1", "PREMIERE_2", "TRIPLE",
}

# Tipos de uso validos
TIPOS_USO_VALIDOS = {
    "Residential",
}

# Tipos de garantia validos para aluguel
GARANTIAS_VALIDAS = {
    "SECURITY_DEPOSIT", "GUARANTOR", "INSURANCE_GUARANTEE",
    "GUARANTEE_LETTER", "CAPITALIZATION_BONDS",
}

# Tipos de imovel que exigem numero de banheiros
EXIGE_BANHEIROS = {
    "Residential / Apartment", "Residential / Home", "Residential / Condo",
    "Residential / Village House", "Residential / Farm Ranch",
    "Residential / Penthouse", "Residential / Flat", "Residential / Kitnet",
    "Residential / Loft", "Residential / Sobrado", "Residential / Agricultural",
}

# Tipos de imovel que exigem numero de quartos
EXIGE_QUARTOS = {
    "Residential / Apartment", "Residential / Home", "Residential / Condo",
    "Residential / Village House", "Residential / Farm Ranch",
    "Residential / Penthouse", "Residential / Flat", "Residential / Kitnet",
    "Residential / Loft", "Residential / Sobrado", "Residential / Agricultural",
}

# Tipos de imovel que usam LotArea em vez de LivingArea
TIPOS_QUE_USAM_LOT_AREA = {
    "Residential / Land Lot",
    "Commercial / Land Lot",
    "Commercial / Industrial",
    "Residential / Farm Ranch",
    "Residential / Agricultural",
}

# Namespace padrao do formato VRSync
NS_VRSYNC = "http://www.vivareal.com/schemas/1.0/VRSync"

_RE_HTML_TAG = re.compile(r"<[a-zA-Z/]")


# ---------------------------------------------------------------------------
# Funcoes auxiliares
# ---------------------------------------------------------------------------

def _texto(elemento: ET.Element, tag: str) -> Optional[str]:
    """Retorna o texto de uma tag filha, ou None se nao existir."""
    filho = elemento.find(tag)
    if filho is None:
        return None
    texto = filho.text
    if texto is None:
        return None
    return texto.strip()


def _texto_ns(elemento: ET.Element, tag: str, ns: str) -> Optional[str]:
    """Retorna o texto de uma tag filha com namespace."""
    filho = elemento.find(f"{{{ns}}}{tag}")
    if filho is None:
        return None
    texto = filho.text
    if texto is None:
        return None
    return texto.strip()


def _valor_numerico(texto: Optional[str]) -> bool:
    """Verifica se o texto e um numero inteiro valido (sem simbolos)."""
    if not texto:
        return False
    stripped = texto.strip()
    return len(stripped) > 0 and stripped.isdigit()


def _url_valida(url: Optional[str]) -> bool:
    """Verificacao basica se uma string parece uma URL valida."""
    if not url:
        return False
    url = url.strip()
    return url.startswith("http://") or url.startswith("https://")


# ---------------------------------------------------------------------------
# Validacoes por secao
# ---------------------------------------------------------------------------

def _validar_header(raiz: ET.Element, ns: str, problemas: list[Problema]) -> None:
    """Valida o elemento Header do feed VRSync."""
    header = raiz.find(f"{{{ns}}}Header") if ns else raiz.find("Header")
    if header is None:
        problemas.append(Problema(
            severidade=Severidade.AVISO,
            campo="Header",
            mensagem="Elemento Header nao encontrado. "
                     "O header e recomendado para identificacao do feed.",
        ))
        return

    # Verifica o elemento Provider (nome da imobiliaria)
    tag_provider = f"{{{ns}}}Provider" if ns else "Provider"
    provider = header.find(tag_provider)
    if provider is None:
        problemas.append(Problema(
            severidade=Severidade.AVISO,
            campo="Header/Provider",
            mensagem="O elemento Provider (nome da imobiliaria) nao foi informado no Header.",
        ))


def _validar_listing_id(listing: ET.Element, ns: str) -> Optional[str]:
    """Extrai e valida o ListingID. Retorna o ID ou None."""
    tag = f"{{{ns}}}ListingID" if ns else "ListingID"
    elem = listing.find(tag)
    if elem is None or not elem.text:
        return None
    imovel_id = elem.text.strip()
    if len(imovel_id) > 50:
        return imovel_id  # O chamador vai validar o tamanho
    return imovel_id


def _validar_title(listing: ET.Element, ns: str, resultado: ResultadoImovel) -> None:
    """Valida o elemento Title."""
    tag = f"{{{ns}}}Title" if ns else "Title"
    elem = listing.find(tag)

    if elem is None or not elem.text:
        resultado.problemas.append(Problema(
            severidade=Severidade.AVISO,
            campo="Title",
            mensagem="Titulo do imovel (Title) nao informado.",
            imovel_id=resultado.imovel_id,
        ))
        return

    titulo = elem.text.strip()

    if len(titulo) < 10:
        resultado.problemas.append(Problema(
            severidade=Severidade.ERRO,
            campo="Title",
            mensagem=f"Titulo muito curto ({len(titulo)} caracteres). "
                     "O minimo e 10 e o maximo e 100 caracteres.",
            imovel_id=resultado.imovel_id,
        ))
    elif len(titulo) > 100:
        resultado.problemas.append(Problema(
            severidade=Severidade.ERRO,
            campo="Title",
            mensagem=f"Titulo muito longo ({len(titulo)} caracteres). "
                     "O maximo e 100 caracteres.",
            imovel_id=resultado.imovel_id,
        ))

    # Verifica tags HTML no titulo (nao sao permitidas)
    if _RE_HTML_TAG.search(titulo):
        resultado.problemas.append(Problema(
            severidade=Severidade.ERRO,
            campo="Title",
            mensagem="O titulo contem tags HTML, o que nao e permitido.",
            imovel_id=resultado.imovel_id,
        ))


def _validar_transaction_type(
    listing: ET.Element, ns: str, resultado: ResultadoImovel
) -> Optional[str]:
    """Valida o TransactionType e retorna o valor encontrado."""
    tag = f"{{{ns}}}TransactionType" if ns else "TransactionType"
    elem = listing.find(tag)

    if elem is None or not elem.text:
        resultado.problemas.append(Problema(
            severidade=Severidade.ERRO,
            campo="TransactionType",
            mensagem="Tipo de transacao (TransactionType) nao informado. "
                     "Valores aceitos: 'For Rent'",
            imovel_id=resultado.imovel_id,
        ))
        return None

    valor = elem.text.strip()
    if valor not in TIPOS_TRANSACAO_VALIDOS:
        resultado.problemas.append(Problema(
            severidade=Severidade.ERRO,
            campo="TransactionType",
            mensagem=f"Tipo de transacao invalido: '{valor}'. "
                     "Valores aceitos: 'For Rent'",
            imovel_id=resultado.imovel_id,
        ))
        return None

    return valor


def _validar_location(listing: ET.Element, ns: str, resultado: ResultadoImovel) -> None:
    """Valida o elemento Location com todos os subelementos obrigatorios."""
    tag = f"{{{ns}}}Location" if ns else "Location"
    location = listing.find(tag)

    if location is None:
        resultado.problemas.append(Problema(
            severidade=Severidade.ERRO,
            campo="Location",
            mensagem="Elemento Location nao encontrado. "
                     "Pais, Estado, Cidade e Bairro sao obrigatorios.",
            imovel_id=resultado.imovel_id,
        ))
        return

    # Verifica o atributo displayAddress
    display_address = location.get("displayAddress")
    if display_address and display_address not in ("All", "Street", "Neighborhood"):
        resultado.problemas.append(Problema(
            severidade=Severidade.AVISO,
            campo="Location[displayAddress]",
            mensagem=f"Valor invalido para displayAddress: '{display_address}'. "
                     "Valores aceitos: 'All', 'Street', 'Neighborhood'.",
            imovel_id=resultado.imovel_id,
        ))

    # Campos obrigatorios minimos
    campos_obrigatorios = {
        "Country": "Pais (Country)",
        "State": "Estado (State)",
        "City": "Cidade (City)",
        "Neighborhood": "Bairro (Neighborhood)",
    }

    for tag_campo, descricao in campos_obrigatorios.items():
        tag_completa = f"{{{ns}}}{tag_campo}" if ns else tag_campo
        elem = location.find(tag_completa)
        if elem is None or not elem.text or not elem.text.strip():
            resultado.problemas.append(Problema(
                severidade=Severidade.ERRO,
                campo=f"Location/{tag_campo}",
                mensagem=f"Campo obrigatorio ausente: {descricao}.",
                imovel_id=resultado.imovel_id,
            ))

    # PostalCode e obrigatorio em todos os imoveis
    tag_cep = f"{{{ns}}}PostalCode" if ns else "PostalCode"
    cep_elem = location.find(tag_cep)
    if cep_elem is None or not cep_elem.text or not cep_elem.text.strip():
        resultado.problemas.append(Problema(
            severidade=Severidade.ERRO,
            campo="Location/PostalCode",
            mensagem="CEP (PostalCode) e obrigatorio em todos os anuncios.",
            imovel_id=resultado.imovel_id,
        ))

    # Latitude e Longitude: se um existe, o outro deve existir
    tag_lat = f"{{{ns}}}Latitude" if ns else "Latitude"
    tag_lng = f"{{{ns}}}Longitude" if ns else "Longitude"
    lat_elem = location.find(tag_lat)
    lng_elem = location.find(tag_lng)
    tem_lat = lat_elem is not None and lat_elem.text and lat_elem.text.strip()
    tem_lng = lng_elem is not None and lng_elem.text and lng_elem.text.strip()

    if tem_lat and not tem_lng:
        resultado.problemas.append(Problema(
            severidade=Severidade.AVISO,
            campo="Location/Longitude",
            mensagem="Latitude informada sem Longitude. "
                     "Ambas devem ser enviadas para posicionamento no mapa.",
            imovel_id=resultado.imovel_id,
        ))
    elif tem_lng and not tem_lat:
        resultado.problemas.append(Problema(
            severidade=Severidade.AVISO,
            campo="Location/Latitude",
            mensagem="Longitude informada sem Latitude. "
                     "Ambas devem ser enviadas para posicionamento no mapa.",
            imovel_id=resultado.imovel_id,
        ))


def _validar_media(listing: ET.Element, ns: str, resultado: ResultadoImovel) -> None:
    """Valida o elemento Media (fotos e videos)."""
    tag = f"{{{ns}}}Media" if ns else "Media"
    media = listing.find(tag)

    if media is None:
        resultado.problemas.append(Problema(
            severidade=Severidade.ERRO,
            campo="Media",
            mensagem="Elemento Media ausente. "
                     "Todos os imoveis devem ter ao menos 1 imagem.",
            imovel_id=resultado.imovel_id,
        ))
        return

    tag_item = f"{{{ns}}}Item" if ns else "Item"
    itens = media.findall(tag_item)

    imagens = [i for i in itens if i.get("medium") == "image"]
    videos = [i for i in itens if i.get("medium") == "video"]

    if not imagens:
        resultado.problemas.append(Problema(
            severidade=Severidade.ERRO,
            campo="Media/Item",
            mensagem="Nenhuma imagem encontrada. "
                     "Ao menos 1 imagem e obrigatoria (medium=\"image\").",
            imovel_id=resultado.imovel_id,
        ))

    # Verifica se ha exatamente uma imagem marcada como primaria
    primarias = [i for i in imagens if i.get("primary") == "true"]
    if imagens and not primarias:
        resultado.problemas.append(Problema(
            severidade=Severidade.AVISO,
            campo="Media/Item[primary]",
            mensagem="Nenhuma foto de destaque definida. "
                     'Marque uma imagem com primary="true".',
            imovel_id=resultado.imovel_id,
        ))
    elif len(primarias) > 1:
        resultado.problemas.append(Problema(
            severidade=Severidade.ERRO,
            campo="Media/Item[primary]",
            mensagem=f"{len(primarias)} imagens marcadas como primary=true. "
                     "Apenas uma pode ser a foto de destaque.",
            imovel_id=resultado.imovel_id,
        ))

    # Verifica URLs das imagens
    for i, img in enumerate(imagens, start=1):
        url = img.text.strip() if img.text else ""
        if not _url_valida(url):
            resultado.problemas.append(Problema(
                severidade=Severidade.ERRO,
                campo=f"Media/Item[image #{i}]",
                mensagem=f"URL de imagem invalida ou vazia: '{url}'.",
                imovel_id=resultado.imovel_id,
            ))
        elif not url.lower().endswith(".jpg"):
            resultado.problemas.append(Problema(
                severidade=Severidade.AVISO,
                campo=f"Media/Item[image #{i}]",
                mensagem=f"A imagem '{url}' nao parece ser JPG. "
                         "Somente imagens .jpg sao aceitas.",
                imovel_id=resultado.imovel_id,
            ))

    # Verifica videos (somente YouTube e aceito; maximo 1)
    if len(videos) > 1:
        resultado.problemas.append(Problema(
            severidade=Severidade.ERRO,
            campo="Media/Item[video]",
            mensagem=f"{len(videos)} videos encontrados. "
                     "Somente um video por imovel e permitido.",
            imovel_id=resultado.imovel_id,
        ))
    for video in videos:
        url_video = video.text.strip() if video.text else ""
        if "youtube.com" not in url_video and "youtu.be" not in url_video:
            resultado.problemas.append(Problema(
                severidade=Severidade.ERRO,
                campo="Media/Item[video]",
                mensagem=f"Video '{url_video}' nao e do YouTube. "
                         "Somente videos do YouTube sao aceitos.",
                imovel_id=resultado.imovel_id,
            ))


def _validar_contact_info(
    listing: ET.Element, ns: str, resultado: ResultadoImovel
) -> None:
    """Valida o elemento ContactInfo."""
    tag = f"{{{ns}}}ContactInfo" if ns else "ContactInfo"
    contact = listing.find(tag)

    if contact is None:
        resultado.problemas.append(Problema(
            severidade=Severidade.ERRO,
            campo="ContactInfo",
            mensagem="Elemento ContactInfo nao encontrado. "
                     "Nome e Email da imobiliaria sao obrigatorios.",
            imovel_id=resultado.imovel_id,
        ))
        return

    # Nome e email sao obrigatorios
    # A documentacao usa <n> para Name dentro de ContactInfo
    for tag_campo, descricao in [("Name", "Nome (Name)"), ("Email", "Email (Email)")]:
        tag_completa = f"{{{ns}}}{tag_campo}" if ns else tag_campo
        elem = contact.find(tag_completa)
        if elem is None or not elem.text or not elem.text.strip():
            resultado.problemas.append(Problema(
                severidade=Severidade.ERRO,
                campo=f"ContactInfo/{tag_campo}",
                mensagem=f"Campo obrigatorio ausente no ContactInfo: {descricao}.",
                imovel_id=resultado.imovel_id,
            ))

    # Valida formato basico do email
    tag_email = f"{{{ns}}}Email" if ns else "Email"
    email_elem = contact.find(tag_email)
    if email_elem is not None and email_elem.text:
        email = email_elem.text.strip()
        if "@" not in email or "." not in email.split("@")[-1]:
            resultado.problemas.append(Problema(
                severidade=Severidade.ERRO,
                campo="ContactInfo/Email",
                mensagem=f"Email invalido: '{email}'.",
                imovel_id=resultado.imovel_id,
            ))


def _validar_details(
    listing: ET.Element,
    ns: str,
    tipo_transacao: Optional[str],
    tipo_imovel: Optional[str],
    resultado: ResultadoImovel,
) -> None:
    """Valida o elemento Details e todos os seus subelementos."""
    tag = f"{{{ns}}}Details" if ns else "Details"
    details = listing.find(tag)

    if details is None:
        resultado.problemas.append(Problema(
            severidade=Severidade.ERRO,
            campo="Details",
            mensagem="Elemento Details nao encontrado. "
                     "Tipo de imovel, area e descricao sao obrigatorios.",
            imovel_id=resultado.imovel_id,
        ))
        return

    _validar_property_type(details, ns, resultado, tipo_imovel)
    _validar_description(details, ns, resultado)
    _validar_area(details, ns, resultado, tipo_imovel)
    _validar_precos(details, ns, resultado, tipo_transacao)
    _validar_quartos_banheiros(details, ns, resultado, tipo_imovel)
    _validar_usage_type(details, ns, resultado)
    _validar_garantias(details, ns, resultado, tipo_transacao)


def _validar_property_type(
    details: ET.Element,
    ns: str,
    resultado: ResultadoImovel,
    tipo_imovel_out: Optional[str],
) -> None:
    """Valida o PropertyType dentro de Details."""
    tag = f"{{{ns}}}PropertyType" if ns else "PropertyType"
    elem = details.find(tag)

    if elem is None or not elem.text:
        resultado.problemas.append(Problema(
            severidade=Severidade.ERRO,
            campo="Details/PropertyType",
            mensagem="Tipo de imovel (PropertyType) e obrigatorio. "
                     "Exemplo: 'Residential / Apartment'.",
            imovel_id=resultado.imovel_id,
        ))
        return

    valor = elem.text.strip()
    if valor not in TIPOS_IMOVEL_VALIDOS:
        resultado.problemas.append(Problema(
            severidade=Severidade.ERRO,
            campo="Details/PropertyType",
            mensagem=f"Tipo de imovel invalido: '{valor}'. "
                     "Consulte a documentacao para a lista de valores aceitos "
                     "(ex: 'Residential / Apartment').",
            imovel_id=resultado.imovel_id,
        ))


def _validar_description(
    details: ET.Element, ns: str, resultado: ResultadoImovel
) -> None:
    """Valida o elemento Description."""
    tag = f"{{{ns}}}Description" if ns else "Description"
    elem = details.find(tag)

    if elem is None or (not elem.text and not list(elem)):
        resultado.problemas.append(Problema(
            severidade=Severidade.ERRO,
            campo="Details/Description",
            mensagem="Descricao (Description) e obrigatoria. "
                     "O conteudo deve ter entre 50 e 3000 caracteres.",
            imovel_id=resultado.imovel_id,
        ))
        return

    texto = (elem.text or "").strip()
    tamanho = len(texto)

    if tamanho == 0:
        resultado.problemas.append(Problema(
            severidade=Severidade.ERRO,
            campo="Details/Description",
            mensagem="Descricao vazia. O conteudo deve ter entre 50 e 3000 caracteres.",
            imovel_id=resultado.imovel_id,
        ))
    elif tamanho < 50:
        resultado.problemas.append(Problema(
            severidade=Severidade.ERRO,
            campo="Details/Description",
            mensagem=f"Descricao muito curta ({tamanho} caracteres). Minimo: 50.",
            imovel_id=resultado.imovel_id,
        ))
    elif tamanho > 3000:
        resultado.problemas.append(Problema(
            severidade=Severidade.ERRO,
            campo="Details/Description",
            mensagem=f"Descricao muito longa ({tamanho} caracteres). Maximo: 3000.",
            imovel_id=resultado.imovel_id,
        ))


def _validar_area(
    details: ET.Element,
    ns: str,
    resultado: ResultadoImovel,
    tipo_imovel: Optional[str],
) -> None:
    """Valida LivingArea e LotArea conforme o tipo de imovel."""
    tag_living = f"{{{ns}}}LivingArea" if ns else "LivingArea"
    tag_lot = f"{{{ns}}}LotArea" if ns else "LotArea"
    living_elem = details.find(tag_living)
    lot_elem = details.find(tag_lot)

    usa_lot_area = tipo_imovel in TIPOS_QUE_USAM_LOT_AREA

    if usa_lot_area:
        if lot_elem is None or not lot_elem.text:
            resultado.problemas.append(Problema(
                severidade=Severidade.ERRO,
                campo="Details/LotArea",
                mensagem=f"Para o tipo '{tipo_imovel}' e obrigatorio informar "
                         "a area total (LotArea).",
                imovel_id=resultado.imovel_id,
            ))
    else:
        if living_elem is None or not living_elem.text:
            resultado.problemas.append(Problema(
                severidade=Severidade.ERRO,
                campo="Details/LivingArea",
                mensagem="Area util (LivingArea) e obrigatoria. "
                         "Informe um valor inteiro sem decimais.",
                imovel_id=resultado.imovel_id,
            ))

    # Verifica formato: deve ser numero inteiro sem decimais
    for elem, nome_campo in [(living_elem, "LivingArea"), (lot_elem, "LotArea")]:
        if elem is not None and elem.text:
            valor = elem.text.strip()
            if not _valor_numerico(valor):
                resultado.problemas.append(Problema(
                    severidade=Severidade.ERRO,
                    campo=f"Details/{nome_campo}",
                    mensagem=f"Valor de area invalido: '{valor}'. "
                             "Informe apenas numero inteiro sem decimais, ponto ou virgula. "
                             "Exemplo correto: 75",
                    imovel_id=resultado.imovel_id,
                ))

        # Verifica atributo unit
        if elem is not None and elem.get("unit") != "square metres":
            resultado.problemas.append(Problema(
                severidade=Severidade.ERRO,
                campo=f"Details/{nome_campo}[unit]",
                mensagem=f'O atributo unit de {nome_campo} deve ser "square metres".',
                imovel_id=resultado.imovel_id,
            ))


def _validar_precos(
    details: ET.Element,
    ns: str,
    resultado: ResultadoImovel,
    tipo_transacao: Optional[str],
) -> None:
    """Valida ListPrice e RentalPrice conforme o tipo de transacao."""
    tag_list = f"{{{ns}}}ListPrice" if ns else "ListPrice"
    tag_rent = f"{{{ns}}}RentalPrice" if ns else "RentalPrice"
    list_price_elem = details.find(tag_list)
    rental_price_elem = details.find(tag_rent)

    if tipo_transacao in ("For Sale",):
        if list_price_elem is None or not list_price_elem.text:
            resultado.problemas.append(Problema(
                severidade=Severidade.ERRO,
                campo="Details/ListPrice",
                mensagem=f"Para transacao '{tipo_transacao}' e obrigatorio "
                         "informar o preco de venda (ListPrice).",
                imovel_id=resultado.imovel_id,
            ))

    if tipo_transacao in ("For Rent",):
        if rental_price_elem is None or not rental_price_elem.text:
            resultado.problemas.append(Problema(
                severidade=Severidade.ERRO,
                campo="Details/RentalPrice",
                mensagem=f"Para transacao '{tipo_transacao}' e obrigatorio "
                         "informar o preco de aluguel (RentalPrice).",
                imovel_id=resultado.imovel_id,
            ))

    # Valida formato dos precos (deve ser numero inteiro)
    for elem, nome_campo in [
        (list_price_elem, "ListPrice"),
        (rental_price_elem, "RentalPrice"),
    ]:
        if elem is not None and elem.text:
            valor = elem.text.strip()
            if not _valor_numerico(valor):
                resultado.problemas.append(Problema(
                    severidade=Severidade.ERRO,
                    campo=f"Details/{nome_campo}",
                    mensagem=f"Valor de preco invalido: '{valor}'. "
                             "Informe apenas o numero inteiro sem R$, pontos ou virgulas. "
                             "Exemplo correto: 250000",
                    imovel_id=resultado.imovel_id,
                ))
            # Verifica atributo currency
            if elem.get("currency") != "BRL":
                resultado.problemas.append(Problema(
                    severidade=Severidade.ERRO,
                    campo=f"Details/{nome_campo}[currency]",
                    mensagem=f'O atributo currency de {nome_campo} deve ser "BRL".',
                    imovel_id=resultado.imovel_id,
                ))


def _validar_quartos_banheiros(
    details: ET.Element,
    ns: str,
    resultado: ResultadoImovel,
    tipo_imovel: Optional[str],
) -> None:
    """Valida Bedrooms e Bathrooms conforme o tipo de imovel."""
    tag_bed = f"{{{ns}}}Bedrooms" if ns else "Bedrooms"
    tag_bath = f"{{{ns}}}Bathrooms" if ns else "Bathrooms"

    bed_elem = details.find(tag_bed)
    bath_elem = details.find(tag_bath)

    if tipo_imovel in EXIGE_QUARTOS:
        if bed_elem is None or not bed_elem.text:
            resultado.problemas.append(Problema(
                severidade=Severidade.ERRO,
                campo="Details/Bedrooms",
                mensagem=f"Numero de quartos (Bedrooms) e obrigatorio "
                         f"para o tipo '{tipo_imovel}'.",
                imovel_id=resultado.imovel_id,
            ))

    if tipo_imovel in EXIGE_BANHEIROS:
        if bath_elem is None or not bath_elem.text:
            resultado.problemas.append(Problema(
                severidade=Severidade.ERRO,
                campo="Details/Bathrooms",
                mensagem=f"Numero de banheiros (Bathrooms) e obrigatorio "
                         f"para o tipo '{tipo_imovel}'.",
                imovel_id=resultado.imovel_id,
            ))

    # Regra especial para Studio: minimo 1 quarto
    if tipo_imovel == "Residential / Studio" and bed_elem is not None and bed_elem.text:
        try:
            quartos = int(bed_elem.text.strip())
            if quartos < 1:
                resultado.problemas.append(Problema(
                    severidade=Severidade.ERRO,
                    campo="Details/Bedrooms",
                    mensagem="Para 'Residential / Studio' o numero minimo de quartos e 1.",
                    imovel_id=resultado.imovel_id,
                ))
        except ValueError:
            pass


def _validar_usage_type(
    details: ET.Element, ns: str, resultado: ResultadoImovel
) -> None:
    """Valida o UsageType."""
    tag = f"{{{ns}}}UsageType" if ns else "UsageType"
    elem = details.find(tag)

    if elem is not None and elem.text:
        valor = elem.text.strip()
        if valor not in TIPOS_USO_VALIDOS:
            resultado.problemas.append(Problema(
                severidade=Severidade.AVISO,
                campo="Details/UsageType",
                mensagem=f"Tipo de uso invalido: '{valor}'. "
                         "Valores aceitos: 'Residential'"
                         "'Residential",
                imovel_id=resultado.imovel_id,
            ))


def _validar_garantias(
    details: ET.Element,
    ns: str,
    resultado: ResultadoImovel,
    tipo_transacao: Optional[str],
) -> None:
    """Valida o elemento Warranties para imoveis de aluguel."""
    if tipo_transacao not in ("For Rent",):
        return

    tag_warranties = f"{{{ns}}}Warranties" if ns else "Warranties"
    tag_warranty = f"{{{ns}}}Warranty" if ns else "Warranty"
    warranties_elem = details.find(tag_warranties)

    if warranties_elem is None:
        return  # Garantias sao opcionais, apenas valida se presente

    for warranty_elem in warranties_elem.findall(tag_warranty):
        valor = warranty_elem.text.strip() if warranty_elem.text else ""
        if valor not in GARANTIAS_VALIDAS:
            resultado.problemas.append(Problema(
                severidade=Severidade.ERRO,
                campo="Details/Warranties/Warranty",
                mensagem=f"Tipo de garantia invalido: '{valor}'. "
                         "Valores aceitos: SECURITY_DEPOSIT, GUARANTOR, "
                         "INSURANCE_GUARANTEE, GUARANTEE_LETTER, CAPITALIZATION_BONDS.",
                imovel_id=resultado.imovel_id,
            ))


# ---------------------------------------------------------------------------
# Funcao principal de validacao
# ---------------------------------------------------------------------------

def validar_xml(conteudo: str) -> ResultadoValidacao:
    """
    Valida o conteudo de um XML no formato VRSync.

    Parametros:
        conteudo: String com o conteudo XML a ser validado.

    Retorna:
        ResultadoValidacao com todos os problemas encontrados.
    """
    resultado = ResultadoValidacao()

    # Etapa 1: Verificar se o XML e sintaticamente valido
    try:
        raiz = ET.fromstring(conteudo)
    except ET.ParseError as e:
        resultado.problemas_gerais.append(Problema(
            severidade=Severidade.ERRO,
            campo="XML",
            mensagem=f"XML invalido (erro de sintaxe): {e}",
        ))
        return resultado

    # Etapa 2: Detectar o namespace
    ns = ""
    tag_raiz = raiz.tag
    if tag_raiz.startswith("{"):
        ns_extraido = tag_raiz[1:].split("}")[0]
        if "vivareal" in ns_extraido or "vrsync" in ns_extraido.lower():
            ns = ns_extraido
        else:
            resultado.problemas_gerais.append(Problema(
                severidade=Severidade.AVISO,
                campo="Namespace",
                mensagem=f"Namespace desconhecido: '{ns_extraido}'. "
                         "O formato esperado e VRSync "
                         "(http://www.vivareal.com/schemas/1.0/VRSync).",
            ))
            ns = ns_extraido

    # Verifica se e um ListingDataFeed valido
    nome_raiz = tag_raiz.split("}")[-1] if "}" in tag_raiz else tag_raiz
    if nome_raiz != "ListingDataFeed":
        resultado.problemas_gerais.append(Problema(
            severidade=Severidade.AVISO,
            campo="Elemento Raiz",
            mensagem=f"Elemento raiz e '{nome_raiz}', esperado 'ListingDataFeed'. "
                     "Verifique se o arquivo esta no formato VRSync.",
        ))

    # Etapa 3: Validar Header
    _validar_header(raiz, ns, resultado.problemas_gerais)

    # Etapa 4: Localizar os Listings
    tag_listings = f"{{{ns}}}Listings" if ns else "Listings"
    tag_listing = f"{{{ns}}}Listing" if ns else "Listing"

    listings_elem = raiz.find(tag_listings)
    if listings_elem is None:
        resultado.problemas_gerais.append(Problema(
            severidade=Severidade.ERRO,
            campo="Listings",
            mensagem="Elemento Listings nao encontrado. Nenhum imovel para processar.",
        ))
        return resultado

    listings = listings_elem.findall(tag_listing)
    resultado.total_imoveis = len(listings)

    if not listings:
        resultado.problemas_gerais.append(Problema(
            severidade=Severidade.AVISO,
            campo="Listings",
            mensagem="Nenhum imovel (Listing) encontrado dentro de Listings.",
        ))
        return resultado

    # Etapa 5: Validar cada imovel
    ids_vistos: set[str] = set()
    tag_details = f"{{{ns}}}Details" if ns else "Details"
    tag_property_type = f"{{{ns}}}PropertyType" if ns else "PropertyType"

    for listing in listings:
        imovel_id = _validar_listing_id(listing, ns)
        resultado_imovel = ResultadoImovel(imovel_id=imovel_id)

        if imovel_id:
            if imovel_id in ids_vistos:
                resultado_imovel.problemas.append(Problema(
                    severidade=Severidade.ERRO,
                    campo="ListingID",
                    mensagem=f"ListingID duplicado: '{imovel_id}'. "
                             "Cada imovel deve ter um ID unico.",
                    imovel_id=imovel_id,
                ))
            else:
                ids_vistos.add(imovel_id)

            if len(imovel_id) > 50:
                resultado_imovel.problemas.append(Problema(
                    severidade=Severidade.ERRO,
                    campo="ListingID",
                    mensagem=f"ListingID muito longo ({len(imovel_id)} caracteres). "
                             "Maximo: 50 caracteres.",
                    imovel_id=imovel_id,
                ))
        else:
            resultado_imovel.problemas.append(Problema(
                severidade=Severidade.AVISO,
                campo="ListingID",
                mensagem="ListingID nao informado. "
                         "Recomendado para identificar o imovel em relatorios.",
                imovel_id=None,
            ))

        details_elem = listing.find(tag_details)
        tipo_imovel = None
        if details_elem is not None:
            pt_elem = details_elem.find(tag_property_type)
            if pt_elem is not None and pt_elem.text:
                tipo_imovel = pt_elem.text.strip()

        _validar_title(listing, ns, resultado_imovel)
        tipo_transacao = _validar_transaction_type(listing, ns, resultado_imovel)
        _validar_location(listing, ns, resultado_imovel)
        _validar_media(listing, ns, resultado_imovel)
        _validar_contact_info(listing, ns, resultado_imovel)
        _validar_details(listing, ns, tipo_transacao, tipo_imovel, resultado_imovel)

        resultado.imoveis.append(resultado_imovel)

    return resultado
