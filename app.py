"""
Interface grafica do Validador de XML VRSync para a plataforma Mellro.

Permite ao usuario informar uma URL de um arquivo XML e visualizar
os resultados da validacao diretamente na tela.

Requisitos:
    - Python 3.10 ou superior
    - tkinter (incluso na instalacao padrao do Python)
"""

import threading
import traceback
import tkinter as tk
from tkinter import ttk
from typing import Optional
import urllib.request
import urllib.error

from validator import (
    ResultadoValidacao,
    Severidade,
    validar_xml,
)


# ---------------------------------------------------------------------------
# Constantes de aparencia
# ---------------------------------------------------------------------------

COR_FUNDO = "#1e1e2e"
COR_PAINEL = "#2a2a3e"
COR_BORDA = "#3d3d5c"
COR_TEXTO = "#cdd6f4"
COR_TEXTO_CLARO = "#a6adc8"
COR_ERRO = "#f38ba8"
COR_AVISO = "#fab387"
COR_OK = "#a6e3a1"
COR_DESTAQUE = "#89b4fa"
COR_BOTAO = "#313244"
COR_BOTAO_HOVER = "#45475a"

FONTE_TITULO = ("Segoe UI", 14, "bold")
FONTE_NORMAL = ("Segoe UI", 10)
FONTE_PEQUENA = ("Segoe UI", 9)
FONTE_CODIGO = ("Consolas", 9)

IMOVEIS_POR_PAGINA = 50
MAX_PROBLEMAS_POR_IMOVEL_EXIBIDOS = 5


# ---------------------------------------------------------------------------
# Logica de busca do XML
# ---------------------------------------------------------------------------

def buscar_xml_da_url(url: str) -> tuple[Optional[str], Optional[str]]:
    """
    Faz o download do conteudo XML a partir de uma URL.

    Retorna:
        (conteudo, None) em caso de sucesso.
        (None, mensagem_de_erro) em caso de falha.
    """
    url = url.strip()
    if not url:
        return None, "URL nao informada."

    if not (url.startswith("http://") or url.startswith("https://")):
        return None, "URL invalida. Deve comecar com http:// ou https://"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "MellroXMLValidator/1.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as resposta:
            conteudo_bytes = resposta.read()

        try:
            return conteudo_bytes.decode("utf-8"), None
        except UnicodeDecodeError:
            return conteudo_bytes.decode("latin-1"), None

    except urllib.error.HTTPError as e:
        return None, f"Erro HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return None, f"Nao foi possivel acessar a URL: {e.reason}"
    except TimeoutError:
        return None, "Tempo de espera esgotado ao tentar acessar a URL."
    except Exception as e:
        return None, f"Erro inesperado: {e}"


# ---------------------------------------------------------------------------
# Componentes da interface
# ---------------------------------------------------------------------------

class PainelResultados(tk.Frame):
    """Painel que exibe os resultados da validacao com rolagem."""

    def __init__(self, parent: tk.Widget, **kwargs):
        super().__init__(parent, bg=COR_FUNDO, **kwargs)
        self._scroll_job: Optional[str] = None
        self._criar_widgets()

    def _criar_widgets(self) -> None:
        """Cria o canvas com scrollbar para exibir os resultados."""
        self.canvas = tk.Canvas(self, bg=COR_FUNDO, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.frame_interno = tk.Frame(self.canvas, bg=COR_FUNDO)
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.frame_interno, anchor="nw"
        )
        self.frame_interno.bind("<Configure>", self._ao_redimensionar_frame)
        self.canvas.bind("<Configure>", self._ao_redimensionar_canvas)

        self.bind("<Enter>", self._ativar_scroll_mouse)
        self.bind("<Leave>", self._desativar_scroll_mouse)

    def _ao_redimensionar_frame(self, _event) -> None:
        """Debounce: agenda atualizacao da scrollregion para evitar recalculos repetidos."""
        if self._scroll_job is not None:
            self.after_cancel(self._scroll_job)
        self._scroll_job = self.after(15, self._atualizar_scrollregion)

    def _atualizar_scrollregion(self) -> None:
        self._scroll_job = None
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _ao_redimensionar_canvas(self, event) -> None:
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _ativar_scroll_mouse(self, _event) -> None:
        self.canvas.bind_all("<MouseWheel>", self._ao_rolar_mouse)

    def _desativar_scroll_mouse(self, _event) -> None:
        self.canvas.unbind_all("<MouseWheel>")

    def _ao_rolar_mouse(self, event) -> None:
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def limpar(self) -> None:
        """Remove todos os widgets do painel de resultados."""
        if self._scroll_job is not None:
            self.after_cancel(self._scroll_job)
            self._scroll_job = None
        self.frame_interno.destroy()
        self.frame_interno = tk.Frame(self.canvas, bg=COR_FUNDO)
        self.canvas.itemconfig(self.canvas_window, window=self.frame_interno)
        self.frame_interno.bind("<Configure>", self._ao_redimensionar_frame)
        self.canvas.configure(scrollregion=(0, 0, 0, 0))
        self.canvas.yview_moveto(0)

    def adicionar_resumo(self, resultado: ResultadoValidacao) -> None:
        """Adiciona o card de resumo ao topo do painel."""
        frame_resumo = tk.Frame(
            self.frame_interno, bg=COR_PAINEL, relief="flat", bd=0
        )
        frame_resumo.pack(fill="x", padx=12, pady=(12, 6))

        cor_status = COR_OK if resultado.imoveis_com_erro == 0 else COR_ERRO
        tk.Frame(frame_resumo, bg=cor_status, height=4).pack(fill="x")

        frame_conteudo = tk.Frame(frame_resumo, bg=COR_PAINEL)
        frame_conteudo.pack(fill="x", padx=16, pady=12)

        tk.Label(
            frame_conteudo,
            text="Resumo da Validacao",
            font=FONTE_TITULO,
            bg=COR_PAINEL,
            fg=COR_TEXTO,
        ).pack(anchor="w")

        frame_metricas = tk.Frame(frame_conteudo, bg=COR_PAINEL)
        frame_metricas.pack(fill="x", pady=(8, 0))

        metricas = [
            ("Total de imoveis", str(resultado.total_imoveis), COR_DESTAQUE),
            ("Com erro (nao importam)", str(resultado.imoveis_com_erro), COR_ERRO),
            ("Sem problemas", str(resultado.imoveis_sem_problema), COR_OK),
            (
                "Erros gerais",
                str(len(resultado.problemas_gerais)),
                COR_AVISO if resultado.problemas_gerais else COR_OK,
            ),
        ]

        for i, (rotulo, valor, cor) in enumerate(metricas):
            col = tk.Frame(frame_metricas, bg=COR_PAINEL)
            col.grid(row=0, column=i, padx=(0, 24))
            tk.Label(
                col, text=valor, font=("Segoe UI", 20, "bold"),
                bg=COR_PAINEL, fg=cor
            ).pack(anchor="w")
            tk.Label(
                col, text=rotulo, font=FONTE_PEQUENA,
                bg=COR_PAINEL, fg=COR_TEXTO_CLARO
            ).pack(anchor="w")

    def adicionar_problemas_gerais(self, resultado: ResultadoValidacao) -> None:
        """Adiciona a secao de problemas gerais (header, estrutura)."""
        if not resultado.problemas_gerais:
            return

        frame = tk.Frame(self.frame_interno, bg=COR_PAINEL)
        frame.pack(fill="x", padx=12, pady=6)
        tk.Frame(frame, bg=COR_AVISO, height=3).pack(fill="x")

        frame_corpo = tk.Frame(frame, bg=COR_PAINEL)
        frame_corpo.pack(fill="x", padx=16, pady=8)

        tk.Label(
            frame_corpo,
            text="Problemas no Arquivo (estrutura geral)",
            font=("Segoe UI", 11, "bold"),
            bg=COR_PAINEL,
            fg=COR_TEXTO,
        ).pack(anchor="w", pady=(0, 6))

        for problema in resultado.problemas_gerais:
            self._adicionar_linha_problema(frame_corpo, problema)

    def adicionar_imovel(self, resultado_imovel, indice: int) -> None:
        """Adiciona o card de resultado de um imovel especifico."""
        tem_erro = resultado_imovel.tem_erros
        tem_aviso = resultado_imovel.tem_avisos
        imovel_id = resultado_imovel.imovel_id or f"#{indice + 1} (sem ID)"

        if tem_erro:
            cor_barra = COR_ERRO
            icone_status = "ERRO"
        elif tem_aviso:
            cor_barra = COR_AVISO
            icone_status = "AVISO"
        else:
            cor_barra = COR_OK
            icone_status = "OK"

        frame = tk.Frame(self.frame_interno, bg=COR_PAINEL)
        frame.pack(fill="x", padx=12, pady=4)
        tk.Frame(frame, bg=cor_barra, height=3).pack(fill="x")

        frame_corpo = tk.Frame(frame, bg=COR_PAINEL)
        frame_corpo.pack(fill="x", padx=16, pady=8)

        frame_header = tk.Frame(frame_corpo, bg=COR_PAINEL)
        frame_header.pack(fill="x", pady=(0, 4))

        tk.Label(
            frame_header,
            text=f"Imovel: {imovel_id}",
            font=("Segoe UI", 10, "bold"),
            bg=COR_PAINEL,
            fg=COR_TEXTO,
        ).pack(side="left")

        tk.Label(
            frame_header,
            text=icone_status,
            font=FONTE_PEQUENA,
            bg=cor_barra,
            fg="#1e1e2e",
            padx=6,
            pady=2,
        ).pack(side="right")

        if not resultado_imovel.problemas:
            tk.Label(
                frame_corpo,
                text="Nenhum problema encontrado. Imovel pronto para importacao.",
                font=FONTE_NORMAL,
                bg=COR_PAINEL,
                fg=COR_OK,
            ).pack(anchor="w")
        else:
            problemas_exibidos = resultado_imovel.problemas[
                :MAX_PROBLEMAS_POR_IMOVEL_EXIBIDOS
            ]
            for problema in problemas_exibidos:
                self._adicionar_linha_problema(frame_corpo, problema)

            qtd_ocultos = len(resultado_imovel.problemas) - len(problemas_exibidos)
            if qtd_ocultos > 0:
                tk.Label(
                    frame_corpo,
                    text=f"... e mais {qtd_ocultos} problema(s) neste imovel.",
                    font=FONTE_PEQUENA,
                    bg=COR_PAINEL,
                    fg=COR_TEXTO_CLARO,
                    anchor="w",
                ).pack(anchor="w", pady=(4, 0))

    def _adicionar_linha_problema(self, parent: tk.Widget, problema) -> None:
        """Adiciona uma linha descrevendo um problema especifico."""
        cor = COR_ERRO if problema.severidade == Severidade.ERRO else COR_AVISO
        prefixo = "[ERRO]" if problema.severidade == Severidade.ERRO else "[AVISO]"

        frame_linha = tk.Frame(parent, bg=COR_PAINEL)
        frame_linha.pack(fill="x", pady=2)

        tk.Label(
            frame_linha,
            text=prefixo,
            font=("Segoe UI", 8, "bold"),
            bg=COR_PAINEL,
            fg=cor,
            width=7,
            anchor="w",
        ).pack(side="left")

        tk.Label(
            frame_linha,
            text=f"{problema.campo}:",
            font=FONTE_CODIGO,
            bg=COR_PAINEL,
            fg=COR_DESTAQUE,
            anchor="w",
        ).pack(side="left", padx=(4, 0))

        tk.Label(
            frame_linha,
            text=problema.mensagem,
            font=FONTE_NORMAL,
            bg=COR_PAINEL,
            fg=COR_TEXTO_CLARO,
            wraplength=620,
            justify="left",
            anchor="w",
        ).pack(side="left", padx=(8, 0), fill="x", expand=True)


# ---------------------------------------------------------------------------
# Janela principal
# ---------------------------------------------------------------------------

class AplicacaoValidador(tk.Tk):
    """Janela principal do validador de XML Mellro."""

    def __init__(self):
        super().__init__()
        self.title("Validador de XML - Mellro / VRSync")
        self.geometry("820x700")
        self.minsize(700, 500)
        self.configure(bg=COR_FUNDO)

        self._configurar_estilos()
        self._criar_interface()

        self._resultado_atual: Optional[ResultadoValidacao] = None
        self._imoveis_filtrados: list = []
        self._pagina_atual = 0
        self._total_paginas = 0

    def _configurar_estilos(self) -> None:
        """Configura os estilos do ttk para o tema escuro."""
        estilo = ttk.Style(self)
        estilo.theme_use("clam")
        estilo.configure(
            "TScrollbar",
            background=COR_BOTAO,
            troughcolor=COR_FUNDO,
            arrowcolor=COR_TEXTO_CLARO,
        )

    def _criar_interface(self) -> None:
        """Cria todos os elementos da interface."""
        # Cabecalho
        frame_header = tk.Frame(self, bg=COR_PAINEL, pady=16)
        frame_header.pack(fill="x")

        tk.Label(
            frame_header,
            text="Validador de XML - Mellro",
            font=("Segoe UI", 16, "bold"),
            bg=COR_PAINEL,
            fg=COR_TEXTO,
        ).pack()

        tk.Label(
            frame_header,
            text="Formato VRSync (Formato de exportacao do VivaReal)",
            font=FONTE_PEQUENA,
            bg=COR_PAINEL,
            fg=COR_TEXTO_CLARO,
        ).pack()

        # Area de entrada da URL
        frame_entrada = tk.Frame(self, bg=COR_FUNDO, pady=12, padx=12)
        frame_entrada.pack(fill="x")

        tk.Label(
            frame_entrada,
            text="URL do arquivo XML:",
            font=FONTE_NORMAL,
            bg=COR_FUNDO,
            fg=COR_TEXTO,
        ).pack(anchor="w")

        frame_campo = tk.Frame(frame_entrada, bg=COR_FUNDO)
        frame_campo.pack(fill="x", pady=(4, 0))

        self.entrada_url = tk.Entry(
            frame_campo,
            font=FONTE_NORMAL,
            bg=COR_BOTAO,
            fg=COR_TEXTO,
            insertbackground=COR_TEXTO,
            relief="flat",
            highlightthickness=1,
            highlightbackground=COR_BORDA,
            highlightcolor=COR_DESTAQUE,
        )
        self.entrada_url.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        self.entrada_url.bind("<Return>", lambda e: self._iniciar_validacao())

        self.botao_validar = tk.Button(
            frame_campo,
            text="Validar",
            font=("Segoe UI", 10, "bold"),
            bg=COR_DESTAQUE,
            fg="#1e1e2e",
            activebackground=COR_BOTAO_HOVER,
            relief="flat",
            cursor="hand2",
            padx=16,
            pady=6,
            command=self._iniciar_validacao,
        )
        self.botao_validar.pack(side="right")

        self.var_apenas_com_problema = tk.BooleanVar(value=True)
        tk.Checkbutton(
            frame_entrada,
            text="Exibir apenas imoveis com problema",
            variable=self.var_apenas_com_problema,
            bg=COR_FUNDO,
            fg=COR_TEXTO_CLARO,
            selectcolor=COR_PAINEL,
            activebackground=COR_FUNDO,
            activeforeground=COR_TEXTO,
            font=FONTE_PEQUENA,
        ).pack(anchor="w", pady=(8, 0))

        # Barra de status
        self.var_status = tk.StringVar(value="Informe a URL do XML e clique em Validar.")
        self.label_status = tk.Label(
            self,
            textvariable=self.var_status,
            font=FONTE_PEQUENA,
            bg=COR_FUNDO,
            fg=COR_TEXTO_CLARO,
            anchor="w",
            padx=12,
        )
        self.label_status.pack(fill="x")

        # Barra de progresso (escondida por padrao)
        self.barra_progresso = ttk.Progressbar(
            self, mode="indeterminate", length=200
        )

        # Barra de paginacao (escondida por padrao)
        self.frame_paginacao = tk.Frame(self, bg=COR_PAINEL, padx=12, pady=6)
        self._criar_controles_paginacao()

        # Separador
        self.separador = tk.Frame(self, bg=COR_BORDA, height=1)
        self.separador.pack(fill="x")

        # Painel de resultados
        self.painel_resultados = PainelResultados(self)
        self.painel_resultados.pack(fill="both", expand=True)

    def _criar_controles_paginacao(self) -> None:
        """Cria botoes e label da barra de paginacao."""
        self.botao_anterior = tk.Button(
            self.frame_paginacao,
            text="< Anterior",
            font=FONTE_PEQUENA,
            bg=COR_BOTAO,
            fg=COR_TEXTO,
            activebackground=COR_BOTAO_HOVER,
            activeforeground=COR_TEXTO,
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=2,
            command=self._pagina_anterior,
        )
        self.botao_anterior.pack(side="left")

        self.label_pagina = tk.Label(
            self.frame_paginacao,
            text="",
            font=FONTE_PEQUENA,
            bg=COR_PAINEL,
            fg=COR_TEXTO_CLARO,
        )
        self.label_pagina.pack(side="left", fill="x", expand=True)

        self.botao_proxima = tk.Button(
            self.frame_paginacao,
            text="Proxima >",
            font=FONTE_PEQUENA,
            bg=COR_BOTAO,
            fg=COR_TEXTO,
            activebackground=COR_BOTAO_HOVER,
            activeforeground=COR_TEXTO,
            relief="flat",
            cursor="hand2",
            padx=10,
            pady=2,
            command=self._proxima_pagina,
        )
        self.botao_proxima.pack(side="right")

    # -- Validacao ----------------------------------------------------------

    def _iniciar_validacao(self) -> None:
        """Dispara a validacao em uma thread separada para nao travar a UI."""
        url = self.entrada_url.get().strip()
        if not url:
            self._atualizar_status("Informe uma URL valida antes de validar.", COR_AVISO)
            return

        self._resultado_atual = None
        self._imoveis_filtrados = []
        self.frame_paginacao.pack_forget()

        self.botao_validar.configure(state="disabled", text="Validando...")
        self.barra_progresso.pack(fill="x", padx=12, pady=4)
        self.barra_progresso.start(10)
        self._atualizar_status(f"Buscando o XML em: {url}", COR_TEXTO_CLARO)
        self.painel_resultados.limpar()

        thread = threading.Thread(
            target=self._executar_validacao,
            args=(url,),
            daemon=True,
        )
        thread.start()

    def _executar_validacao(self, url: str) -> None:
        """Executa o download e a validacao em background."""
        try:
            conteudo, erro = buscar_xml_da_url(url)

            if erro:
                self.after(0, self._exibir_erro_download, erro)
                return

            self.after(0, lambda: self._atualizar_status(
                "XML baixado. Validando imoveis...", COR_TEXTO_CLARO
            ))

            resultado = validar_xml(conteudo)
            self.after(0, self._exibir_resultado, resultado)
        except Exception as e:
            tb = traceback.format_exc()
            self.after(0, self._exibir_erro_download, f"Erro inesperado: {e}\n\n{tb}")

    # -- Exibicao de resultados ---------------------------------------------

    def _exibir_erro_download(self, mensagem: str) -> None:
        """Exibe um erro de download na interface."""
        self._finalizar_carregamento()
        self._atualizar_status(f"Falha ao buscar o XML: {mensagem}", COR_ERRO)

        frame = tk.Frame(
            self.painel_resultados.frame_interno, bg=COR_PAINEL
        )
        frame.pack(fill="x", padx=12, pady=12)
        tk.Frame(frame, bg=COR_ERRO, height=4).pack(fill="x")
        tk.Label(
            frame,
            text=f"Nao foi possivel acessar o XML:\n{mensagem}",
            font=FONTE_NORMAL,
            bg=COR_PAINEL,
            fg=COR_ERRO,
            wraplength=700,
            justify="left",
            padx=16,
            pady=12,
        ).pack(anchor="w")

    def _exibir_resultado(self, resultado: ResultadoValidacao) -> None:
        """Prepara os dados e renderiza a primeira pagina."""
        self._finalizar_carregamento()
        self._resultado_atual = resultado

        total_erros = resultado.imoveis_com_erro
        if total_erros == 0:
            status = (
                f"Validacao concluida: {resultado.total_imoveis} imovel(is) verificado(s). "
                "Nenhum erro critico encontrado."
            )
            cor_status = COR_OK
        else:
            status = (
                f"Validacao concluida: {total_erros} de {resultado.total_imoveis} "
                "imovel(is) com erros que impedem a importacao."
            )
            cor_status = COR_ERRO

        self._atualizar_status(status, cor_status)

        apenas_com_problema = self.var_apenas_com_problema.get()
        self._imoveis_filtrados = [
            (i, r)
            for i, r in enumerate(resultado.imoveis)
            if (r.problemas or not apenas_com_problema)
        ]

        total_filtrado = len(self._imoveis_filtrados)
        self._total_paginas = max(
            1, (total_filtrado + IMOVEIS_POR_PAGINA - 1) // IMOVEIS_POR_PAGINA
        )
        self._pagina_atual = 0

        if total_filtrado > IMOVEIS_POR_PAGINA:
            self.frame_paginacao.pack(fill="x", before=self.separador)
        else:
            self.frame_paginacao.pack_forget()

        self._renderizar_pagina()

    # -- Paginacao ----------------------------------------------------------

    def _renderizar_pagina(self) -> None:
        """Renderiza o resumo e a pagina atual de imoveis."""
        self.painel_resultados.limpar()

        if self._resultado_atual is None:
            return

        self.painel_resultados.adicionar_resumo(self._resultado_atual)
        self.painel_resultados.adicionar_problemas_gerais(self._resultado_atual)

        inicio = self._pagina_atual * IMOVEIS_POR_PAGINA
        fim = inicio + IMOVEIS_POR_PAGINA
        pagina = self._imoveis_filtrados[inicio:fim]

        for indice, resultado_imovel in pagina:
            self.painel_resultados.adicionar_imovel(resultado_imovel, indice)

        self._atualizar_controles_paginacao()

    def _atualizar_controles_paginacao(self) -> None:
        """Atualiza o texto e o estado dos botoes de paginacao."""
        total = len(self._imoveis_filtrados)
        self.label_pagina.configure(
            text=(
                f"Pagina {self._pagina_atual + 1} de {self._total_paginas}  "
                f"({total} imoveis)"
            )
        )
        self.botao_anterior.configure(
            state="normal" if self._pagina_atual > 0 else "disabled"
        )
        self.botao_proxima.configure(
            state="normal" if self._pagina_atual < self._total_paginas - 1 else "disabled"
        )

    def _pagina_anterior(self) -> None:
        if self._pagina_atual > 0:
            self._pagina_atual -= 1
            self._renderizar_pagina()

    def _proxima_pagina(self) -> None:
        if self._pagina_atual < self._total_paginas - 1:
            self._pagina_atual += 1
            self._renderizar_pagina()

    # -- Utilidades ---------------------------------------------------------

    def _finalizar_carregamento(self) -> None:
        """Restaura a interface apos o termino da validacao."""
        self.barra_progresso.stop()
        self.barra_progresso.pack_forget()
        self.botao_validar.configure(state="normal", text="Validar")

    def _atualizar_status(self, mensagem: str, cor: str = COR_TEXTO_CLARO) -> None:
        """Atualiza o texto e a cor da barra de status."""
        self.var_status.set(mensagem)
        self.label_status.configure(fg=cor)


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def main() -> None:
    """Inicializa e executa a aplicacao."""
    app = AplicacaoValidador()
    app.mainloop()


if __name__ == "__main__":
    main()
