# Conversor de Video (Flet + FFmpeg)

Aplicativo desktop em Python para:
- converter videos em lote (fila)
- escolher formato, codec, qualidade e resolucao
- gerar arquivos DVD MPEG-2 (PAL/NTSC)
- criar estrutura `VIDEO_TS` (`.VOB`, `.IFO`, `.BUP`) com `dvdauthor`

## Tecnologias
- Python 3.10+
- [Flet](https://flet.dev/)
- [FFmpeg](https://ffmpeg.org/)
- `dvdauthor` (opcional, para autoria de DVD)

## Estrutura do Projeto
- `interface.py`: frontend/UI (Flet)
- `main.py`: backend/logica de conversao e autoria DVD

## Instalacao
1. Clone o repositorio
2. Instale dependencias Python:

```bash
pip install flet
```

3. Instale FFmpeg e adicione ao `PATH`
4. (Opcional) Instale `dvdauthor`

### Windows + WSL (recomendado para dvdauthor)
No PowerShell (Admin):

```powershell
wsl --install -d Ubuntu
```

No Ubuntu (WSL):

```bash
sudo apt update
sudo apt install -y ffmpeg dvdauthor
```

## Como Executar
```bash
python interface.py
```

## Fluxo de Uso
1. Clique em `Adicionar videos`
2. Escolha formato/codec/qualidade/resolucao
3. (Opcional) Selecione `Perfil para disco DVD`
4. Clique em `Converter fila`
5. Para criar `VIDEO_TS`, clique em `Criar VIDEO_TS`

## Notas
- `dvdauthor` e detectado no Windows ou via WSL automaticamente.
- Em modo DVD, a conversao gera `.mpg` (MPEG-2 compatível).
- A estrutura `VIDEO_TS` e gerada em pasta `DVD_OUTPUT_N`.

## Licenca
Defina a licenca do seu projeto (ex.: MIT) antes de publicar.
