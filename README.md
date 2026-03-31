# Validador de XML - Mellro (formato VRSync)

Ferramenta desktop para validar arquivos XML de imoveis no formato **VRSync**
antes de importa-los na plataforma Mellro.

Identifica erros e avisos que impediriam ou prejudicariam a importacao,
exibindo os problemas campo a campo diretamente na interface.

---

## Requisitos

- **Python 3.10 ou superior**
- **tkinter** (incluso no Python para Windows e macOS)

No Linux (Ubuntu/Debian), instale o tkinter separadamente:

```bash
sudo apt install python3-tk
```

---

## Instalacao

### Windows

1. Baixe e instale o Python em https://python.org/downloads
   - Marque a opcao "Add Python to PATH" durante a instalacao

2. Extraia os arquivos do projeto em uma pasta

3. Abra o Prompt de Comando nessa pasta e execute:

```cmd
python app.py
```

Ou clique duas vezes no arquivo `app.py` se o Python estiver associado.

### macOS

1. Instale o Python pelo site oficial ou via Homebrew:

```bash
brew install python@3.11
```

2. Execute a aplicacao:

```bash
python3 app.py
```

### Linux (Ubuntu/Debian)

1. Instale Python e tkinter:

```bash
sudo apt update
sudo apt install python3 python3-tk
```

2. Execute a aplicacao:

```bash
python3 app.py
```

---

## Como usar

1. Abra a aplicacao executando `python app.py`
2. Cole a URL do arquivo XML no campo de entrada
3. Clique em **Validar** ou pressione **Enter**
4. Aguarde o download e analise do XML
5. Leia os resultados na tela:
   - **ERRO** (vermelho) = impede a importacao do imovel
   - **AVISO** (laranja) = pode causar problemas, mas nao bloqueia

---

## O que e validado

O validador verifica as regras do formato VRSync conforme a documentacao
oficial do Grupo OLX, que e o padrao aceito pela Mellro:

**Estrutura geral:**
- Sintaxe XML valida
- Namespace correto do VRSync
- Presenca do elemento Header

**Por imovel (Listing):**
- `ListingID` - unicidade e tamanho maximo de 50 caracteres
- `Title` - tamanho entre 10 e 100 caracteres, sem HTML
- `TransactionType` - valores aceitos: For Sale, For Rent, Sale/Rent
- `Location` - campos obrigatorios: Country, State, City, Neighborhood, PostalCode
- `Media` - ao menos 1 imagem JPG, apenas 1 foto de destaque, video somente YouTube
- `ContactInfo` - Name e Email obrigatorios
- `Details/PropertyType` - tipo de imovel valido conforme tabela VRSync
- `Details/Description` - entre 50 e 3000 caracteres
- `Details/LivingArea` ou `LotArea` - numero inteiro, atributo unit="square metres"
- `Details/ListPrice` / `RentalPrice` - numero inteiro, atributo currency="BRL"
- `Details/Bedrooms` / `Bathrooms` - obrigatorio conforme o tipo de imovel
- `Details/UsageType` - valores aceitos: Residential, Commercial, etc.
- `Details/Warranties` - garantias validas para imoveis de aluguel

---

## Estrutura do projeto

```
xml_validator/
    app.py          - Interface grafica (janela, painel de resultados)
    validator.py    - Logica de validacao do XML
    requirements.txt
    README.md
```

---

## Manutencao

Para adicionar novas regras de validacao, edite o arquivo `validator.py`.
As funcoes sao divididas por secao do XML (header, listing, details, etc.)
e estao documentadas com docstrings.

Para alterar a aparencia da interface, edite as constantes no topo de `app.py`.
