#!/bin/bash

echo "Iniciando o setup completo do projeto..."

# 1. Cria a Virtual Environment (venv) na raiz do projeto
echo "Criando ambiente virtual (venv)..."
python -m venv .venv

# 2. Ativa a venv dependendo do sistema operacional
echo "Ativando venv..."
if [ -f ".venv/Scripts/activate" ]; then
    # Windows
    source .venv/Scripts/activate
else
    # Linux / macOS
    source .venv/bin/activate
fi

# 3. Atualiza o pip para evitar avisos chatos
python -m pip install --upgrade pip

# 4. Instala os requirements de cada microserviço
echo "Instalando dependências do Backend..."
pip install -r requirements.txt

# 5. Instala os pacotes do frontend
echo "Instalando dependências do Frontend..."
cd frontend
npm install
cd ..

# 6. Instala pacote para rodar processos simultâneos
npm install

echo "Setup concluído com sucesso!"