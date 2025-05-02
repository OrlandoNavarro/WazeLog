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

### 1. (Opcional, mas recomendado) Inicie o Servidor OSRM Local com Docker
Para evitar limites e timeouts do servidor público do OSRM, você pode rodar uma instância local usando Docker. Isso requer o download dos dados do mapa (ex: Brasil) e um pré-processamento inicial que pode demorar.

   a. Navegue até o diretório de configuração do OSRM local:
      ```bash
      cd /workspaces/WazeLog/routing/osrm_local/
      ```
   b. Inicie os serviços Docker Compose:
      ```bash
      docker-compose up
      ```
      Alternativamente, você pode executar os dois passos em um único comando:
      ```bash
      cd /workspaces/WazeLog/routing/osrm_local/ && docker-compose up
      ```
      ```
      cd /workspaces/WazeLog/routing/osrm_local/data/ && wget http://download.geofabrik.de/south-america/brazil/sudeste-latest.osm.pbf && mv sudeste-latest.osm.pbf sao-paulo-latest.osm.pbf

      ```
   c. **Aguarde o Pré-processamento:** Na primeira execução, o Docker baixará a imagem do OSRM e iniciará o pré-processamento dos dados do mapa (`brazil-latest.osm.pbf`). **Este passo pode levar bastante tempo (vários minutos a mais de uma hora)**. Aguarde até ver a mensagem "--- Pré-processamento OSRM concluído com sucesso! ---" no terminal. O container `osrm_preprocess_brazil` deve parar após o sucesso.
   d. **Servidor Rodando:** Após o pré-processamento, o container `osrm_backend_brazil` iniciará automaticamente e ficará escutando na porta `5000`. O código Python já está configurado para usar `http://localhost:5000` quando este servidor estiver ativo.
   e. Para rodar o servidor em background nas próximas vezes (após o pré-processamento inicial):
      ```bash
      # Dentro de /workspaces/WazeLog/routing/osrm_local/
      docker-compose up -d osrm-backend
      ```
   f. Para parar o servidor:
      ```bash
      # cd /workspaces/WazeLog/routing/osrm_local/data/ && wget http://download.geofabrik.de/south-america/brazil/sudeste-latest.osm.pbf && mv sudeste-latest.osm.pbf sao-paulo-latest.osm.pbf
      ```

### 2. Inicie o backend FastAPI
```bash
uvicorn main:app --reload
python -m uvicorn main:app
```
Acesse: http://localhost:8000

### 3. Inicie o frontend Streamlit
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
Agradecemos a todos os contribuidores e usuários que tornam o Wazelog uma ferramenta melhor a cada dia! 🚀
```