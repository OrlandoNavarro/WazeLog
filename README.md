# Wazelog - Roteirizador de Entregas 🚚🗺️

Wazelog é uma plataforma moderna para roteirização inteligente de entregas, combinando backend FastAPI, frontend Streamlit e banco de dados local SQLite. Permite importar, editar, visualizar e gerenciar pedidos e frota, além de gerar e visualizar rotas otimizadas em mapas interativos.

## ✨ Funcionalidades
- Upload, edição e persistência de planilhas de frota e pedidos
- Busca automática de coordenadas (Nominatim/OpenCage)
- Edição manual e visualização dos dados
- Remoção e adição de registros
- Limpeza total dos pedidos e frota
- Visualização de mapas e dashboards
- Geração de rotas otimizadas (VRP, CVRP, VRPTW, TSP)
- Visualização de rotas por veículo/placa
- Exportação de anomalias para CSV

## 📦 Pré-requisitos
- Python 3.10+
- pip

## 🚀 Instalação
1. Clone o repositório ou baixe os arquivos.
2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

## 🏁 Como iniciar o projeto

### 1. Inicie o backend FastAPI
```bash
uvicorn main:app --reload
python - m uvicorn main:app --reload
```
Acesse: http://localhost:8000

### 2. Inicie o frontend Streamlit
```bash
streamlit run app/app.py
python -m streamlit run app/app.py
```
Acesse: http://localhost:8501

## 🗂️ Estrutura de Pastas
- `app/` - Código principal do Streamlit e módulos auxiliares
- `database/` - Banco SQLite local
- `data/` - Planilhas de exemplo ou dados de entrada
- `routing/` - Algoritmos de roteirização e otimização

## 💡 Observações
- O processamento de pedidos pode demorar devido à busca de coordenadas.
- O banco de dados é criado automaticamente em `database/wazelog.db`.
- Para uso em produção, configure variáveis de ambiente para as chaves de API do OpenCage.
- O sistema já traz um endereço de partida padrão, mas pode ser alterado na interface.
- Após a roteirização, visualize rotas por placa na aba "Mapas".

## 👨‍💻 Contribuição
Pull requests são bem-vindos! Para grandes mudanças, abra uma issue primeiro para discutir o que você gostaria de modificar.

---
Desenvolvido por Orlando e colaboradores.
