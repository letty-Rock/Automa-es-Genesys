::: {align="center"}

☁️ Genesys Cloud Automation Toolkit

Automação segura de filas, skills e grupos via Genesys Cloud API

Backup • DRY RUN • Validação • Logs • OAuth Client Credentials
:::

✨ Sobre o projeto

Este projeto reúne scripts Python para automatizar tarefas
administrativas no Genesys Cloud usando a API REST v2.

A proposta é tornar operações em lote mais previsíveis, auditáveis e
seguras. Antes das alterações, o projeto permite gerar backups; os
scripts de escrita trabalham com DRY RUN por padrão, exigem
confirmação para execução real e validam o estado após as chamadas à
API.

[!IMPORTANT] Nunca publique CLIENT_SECRET, credenciais OAuth,
arquivos com usuários reais ou dados internos da organização.

🧭 Visão geral

                   Script                          O que faz        Altera o ambiente?

       📦          `01_exportar_filas_skills.py`   Backup de filas          ❌
                                                   e skills + CSVs 
                                                   normalizados    

       🧹          `02_remover_filas_skills.py`    Remove                   ✅
                                                   associações     
                                                   existentes      

       🧠          `03_adicionar_skills.py`        Adiciona skills          ✅
                                                   e ajusta        
                                                   proficiency     

       👥          `04_adicionar_filas.py`         Adiciona                 ✅
                                                   usuários às     
                                                   filas           

       🏷️          `05_adicionar_grupo.py`         Adiciona                 ✅
                                                   usuários ao     
                                                   grupo           
                                                   configurado     

       🔎          `consulta.py`                   Consulta fila e          ❌
                                                   skill           
                                                   separadamente   

🔄 Fluxo operacional

             ┌──────────────────────────────┐
             │  01 • BACKUP DO AMBIENTE    │
             └──────────────┬───────────────┘
                            ↓
             ┌──────────────────────────────┐
             │  REVISAR CSVs E BACKUPS      │
             └──────────────┬───────────────┘
                            ↓
             ┌──────────────────────────────┐
             │  02 • REMOVER ASSOCIAÇÕES   │
             │       DRY RUN → EXECUTE      │
             └──────────────┬───────────────┘
                            ↓
             ┌──────────────────────────────┐
             │  03 • APLICAR SKILLS         │
             │       DRY RUN → EXECUTE      │
             └──────────────┬───────────────┘
                            ↓
             ┌──────────────────────────────┐
             │  04 • APLICAR FILAS          │
             │       DRY RUN → EXECUTE      │
             └──────────────┬───────────────┘
                            ↓
             ┌──────────────────────────────┐
             │  05 • APLICAR GRUPO          │
             │       DRY RUN → EXECUTE      │
             └──────────────┬───────────────┘
                            ↓
             ┌──────────────────────────────┐
             │  🔎 CONSULTA / VALIDAÇÃO     │
             └──────────────────────────────┘

[!TIP] Execute o 01 antes de qualquer operação em lote e preserve
os arquivos históricos da pasta output.

📁 Estrutura

genesys/
│
├── ⚙️  config.py
├── 🔌 genesys_api.py
│
├── 📄 usuarios.csv
├── 📄 filas.csv
├── 📄 skills.csv
│
├── 📦 01_exportar_filas_skills.py
├── 🧹 02_remover_filas_skills.py
├── 🧠 03_adicionar_skills.py
├── 👥 04_adicionar_filas.py
├── 🏷️  05_adicionar_grupo.py
├── 🔎 consulta.py
│
└── 📂 output/

🚀 Começando

1. Requisitos

Python 3

Biblioteca requests

OAuth Client do Genesys Cloud com as permissões necessárias

py -m pip install requests

2. Configure o ambiente

O config.py centraliza região, credenciais e arquivos utilizados.

SAE1

CLIENT_ID = "SEU_CLIENT_ID"
CLIENT_SECRET = "SEU_CLIENT_SECRET"

REGION = "sae1.pure.cloud"
LOGIN_URL = "https://login.sae1.pure.cloud"
API_URL = "https://api.sae1.pure.cloud"

USERS_FILE = "usuarios.csv"
OUTPUT_DIR = "output"
GROUP_DESTINO = "NOME_EXATO_DO_GRUPO"

USE1

CLIENT_ID = "SEU_CLIENT_ID"
CLIENT_SECRET = "SEU_CLIENT_SECRET"

REGION = "mypurecloud.com"
LOGIN_URL = "https://login.mypurecloud.com"
API_URL = "https://api.mypurecloud.com"

USERS_FILE = "usuarios.csv"
OUTPUT_DIR = "output"
GROUP_DESTINO = "NOME_EXATO_DO_GRUPO"

[!WARNING] CLIENT_ID e CLIENT_SECRET precisam pertencer ao
ambiente indicado por LOGIN_URL e API_URL. Não misture credenciais
entre organizações ou regiões.

🔐 Camada de API

Todos os scripts compartilham GenesysAPI, evitando duplicação de
autenticação e tratamento HTTP.

from genesys_api import GenesysAPI

api = GenesysAPI()
api.autenticar()

dados = api.get("/api/v2/...")
dados = api.post("/api/v2/...", json={...})
dados = api.put("/api/v2/...", json={...})
dados = api.delete("/api/v2/...")

OAuth

POST {LOGIN_URL}/oauth/token
Authorization: Basic base64(CLIENT_ID:CLIENT_SECRET)
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials

O que GenesysAPI centraliza

GET • POST • PUT • DELETE • reautenticação em 401 • tratamento
de 429 • backoff • retry em 500/502/503/504 • paginação • mensagens
detalhadas de erro.

📊 Formato dos dados

👤 usuarios.csv

email
usuario1@empresa.com
usuario2@empresa.com

Usado principalmente pelos scripts 01 e 05.

👥 filas.csv

email;user_id;fila;queue_id
usuario1@empresa.com;UUID_USUARIO;Nome da Fila;UUID_FILA

Cada linha representa uma associação usuário → fila.

user_id e queue_id podem ficar vazios em arquivos montados
manualmente. O script 04 consegue resolver o usuário pelo e-mail e a
fila pelo nome.

🧠 skills.csv

email;user_id;skill;skill_id;proficiency
usuario1@empresa.com;UUID_USUARIO;Nome da Skill;UUID_SKILL;5.0

Cada linha representa uma associação usuário → skill.

A proficiency deve ficar entre 0 e 5. O script 03 resolve a
skill pelo nome no ambiente atual; o skill_id do CSV funciona como
referência e pode ser diferente entre ambientes.

🛠️ Scripts

📦 01 · Exportar filas e skills

Objetivo: registrar o estado atual antes das alterações.

py .\01_exportar_filas_skills.py

Saídas

output\backup_genesys_DATA_HORA.csv
output\filas_DATA_HORA.csv
output\skills_DATA_HORA.csv

filas.csv
skills.csv

Os CSVs normalizados obtêm nome e ID do mesmo objeto retornado pela API,
evitando associações incorretas.

<details>

<summary>

<strong>{=html}Endpoints utilizados</strong>{=html}

</summary>

Método                  Endpoint                                 Uso

POST                  /api/v2/users/search                   Busca exata do usuário

GET                   /api/v2/users/{userId}/queues          Filas do usuário

GET                   /api/v2/users/{userId}/routingskills   Skills e proficiency

</details>

🧹 02 · Remover filas e skills

Objetivo: remover associações existentes com planejamento e
validação posterior.

🧪 DRY RUN

py .\02_remover_filas_skills.py

🔴 Execução real

py .\02_remover_filas_skills.py --execute

Digite:

REMOVER

[!CAUTION] Este script realiza remoções. Revise o plano apresentado
no DRY RUN antes de utilizar --execute.

Após cada alteração, o estado é consultado novamente. A remoção somente
é registrada como confirmada quando o ID deixa de aparecer no estado
atual.

<details>

<summary>

<strong>{=html}Endpoints utilizados</strong>{=html}

</summary>

Método                  Endpoint                                                 Uso

GET                   /api/v2/users/{userId}/queues                          Consulta/validação de
filas

GET                   /api/v2/users/{userId}/routingskills                   Consulta/validação de
skills

DELETE                /api/v2/users/{userId}/routingskills/{skillId}         Remove skill

POST                  /api/v2/routing/queues/{queueId}/members?delete=true   Remove membro da fila

Body da remoção de fila:

[
  {
    "id": "USER_ID"
  }
]

</details>

[!NOTE] A documentação atual registra que o 02 consome o backup
resumido backup_genesys_*.csv. Uma evolução do projeto é fazê-lo
consumir diretamente os backups normalizados.

🧠 03 · Adicionar skills

Objetivo: aplicar as associações de skills.csv e ajustar a
proficiency.

DRY RUN

py .\03_adicionar_skills.py

Execução

py .\03_adicionar_skills.py --execute

Confirmação:

ADICIONAR

O fluxo resolve:

E-mail
  ↓
Usuário
  ↓
Nome da skill
  ↓
Skill do ambiente atual
  ↓
Já existe?
  ├─ NÃO → POST
  └─ SIM → compara proficiency → PUT quando necessário

<details>

<summary>

<strong>{=html}Endpoints utilizados</strong>{=html}

</summary>

Método   Endpoint

POST   /api/v2/users/search
GET    /api/v2/routing/skills
GET    /api/v2/routing/skills/{skillId}
GET    /api/v2/users/{userId}/routingskills
POST   /api/v2/users/{userId}/routingskills
PUT    /api/v2/users/{userId}/routingskills/{skillId}

Exemplo:

{
  "id": "SKILL_ID",
  "name": "NOME_DA_SKILL",
  "proficiency": 5
}

</details>

👥 04 · Adicionar filas

Objetivo: aplicar as associações definidas em filas.csv.

# DRY RUN
py .\04_adicionar_filas.py

# Execução
py .\04_adicionar_filas.py --execute

Confirmação:

ADICIONAR

Para localizar a fila, o script tenta:

queue_id informado
       ↓
   ID válido?
   ├─ SIM → utiliza a fila
   └─ NÃO → procura pelo nome exato

<details>

<summary>

<strong>{=html}Endpoints utilizados</strong>{=html}

</summary>

Método   Endpoint

POST   /api/v2/users/search
GET    /api/v2/routing/queues
GET    /api/v2/routing/queues/{queueId}
GET    /api/v2/users/{userId}/queues
POST   /api/v2/routing/queues/{queueId}/members

Body:

[
  {
    "id": "USER_ID"
  }
]

</details>

🏷️ 05 · Adicionar usuários ao grupo

Objetivo: adicionar os usuários de usuarios.csv ao
GROUP_DESTINO.

# DRY RUN
py .\05_adicionar_grupo.py

# Execução
py .\05_adicionar_grupo.py --execute

Confirmação:

ADICIONAR

O script consulta os membros existentes e ignora usuários que já
pertencem ao grupo.

<details>

<summary>

<strong>{=html}Endpoints utilizados</strong>{=html}

</summary>

Método   Endpoint

POST   /api/v2/users/search
GET    /api/v2/groups
GET    /api/v2/groups/{groupId}/members
POST   /api/v2/groups/{groupId}/members

Body correto:

{
  "memberIds": [
    "USER_ID"
  ]
}

Enviar somente uma lista de strings causou 400 bad.request no
ambiente documentado.

</details>

🔎 Consulta de fila e skill

Gera duas listas independentes:

todos os usuários da fila;

todos os usuários com a skill.

A interseção é apenas informativa.

py .\consulta.py

Arquivos gerados

output\fila_NOME_DA_FILA.csv
output\skill_NOME_DA_SKILL.csv

<details>

<summary>

<strong>{=html}Endpoints utilizados</strong>{=html}

</summary>

Método                  Endpoint                                     Uso

GET                   /api/v2/routing/queues                     Localiza a fila

GET                   /api/v2/routing/skills                     Localiza a skill

GET                   /api/v2/routing/queues/{queueId}/members   Lista membros

</details>

🛡️ Segurança operacional

[!CAUTION] Os scripts 02, 03, 04 e 05 podem alterar dados do
Genesys Cloud. Use o ambiente correto, faça backup e valide o DRY RUN.

Checklist antes de --execute

Executei o script 01

Preservei o backup em output

Conferi REGION, LOGIN_URL e API_URL

Revisei usuarios.csv

Revisei filas.csv / skills.csv

Executei o DRY RUN

Conferi uma amostra dos usuários

Tenho certeza de que estou no ambiente correto

📝 Logs

Script   Confirmação   Log

02     REMOVER     output\remocao_DATA_HORA.csv
03     ADICIONAR   output\adicao_skills_DATA_HORA.csv
04     ADICIONAR   output\adicao_filas_DATA_HORA.csv
05     ADICIONAR   output\adicao_grupo_DATA_HORA.csv

🚨 Troubleshooting

HTTP / Sintoma                      Verifique

🔑 401 Unauthorized               Credenciais, token e região

🚫 403 Forbidden                  Roles/permissões do OAuth Client

🔍 404                            ID, ambiente e associação

⏳ 429 Too Many Requests          Rate limit / Retry-After

⚠️ 400 bad.request no grupo       Body com memberIds

👥 Fila não encontrada              queue_id ou nome exato

🧠 Skill ID diferente               Resolução pelo nome no ambiente
atual

🔒 .gitignore recomendado

Crie um .gitignore antes de publicar o repositório:

# 🔐 Credenciais
config.py
.env

# 👤 Dados operacionais
usuarios.csv
filas.csv
skills.csv
output/

# 🐍 Python
__pycache__/
*.py[cod]
.venv/
venv/

# 💻 IDE / SO
.vscode/
.idea/
.DS_Store
Thumbs.db

[!WARNING] .gitignore não remove segredos que já foram commitados.
Antes de tornar o repositório público, confira também o histórico do
Git.

⚡ Referência rápida

# 01 • Backup
py .\01_exportar_filas_skills.py

# 02 • Remoção
py .\02_remover_filas_skills.py
py .\02_remover_filas_skills.py --execute

# 03 • Skills
py .\03_adicionar_skills.py
py .\03_adicionar_skills.py --execute

# 04 • Filas
py .\04_adicionar_filas.py
py .\04_adicionar_filas.py --execute

# 05 • Grupo
py .\05_adicionar_grupo.py
py .\05_adicionar_grupo.py --execute

# Consulta
py .\consulta.py

🗺️ Roadmap

Algumas evoluções naturais do projeto:

Fazer o script 02 consumir diretamente backups normalizados

Separar configuração pública de credenciais

Adicionar testes automatizados

Criar validação prévia dos CSVs

Adicionar exemplos de arquivos sem dados reais

Criar relatório consolidado após operações em lote

📚 Referência

A documentação deste repositório foi construída a partir dos scripts
desenvolvidos e testados no projeto.

Para contratos oficiais da API, modelos, autenticação e permissões,
consulte o Genesys Cloud Developer Center.

::: {align="center"}

☁️ Genesys Cloud Automation Toolkit

Automação com backup primeiro, validação antes e confirmação depois.
:::
