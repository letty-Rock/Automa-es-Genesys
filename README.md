Automação Genesys Cloud

Automação de tarefas administrativas no Genesys Cloud usando OAuth
Client Credentials e a API REST v2.

O projeto centraliza autenticação, chamadas HTTP e tratamento de erros
em genesys_api.py, enquanto config.py concentra região, credenciais
e caminhos. Os scripts operacionais seguem um fluxo seguro com
backup, DRY RUN, confirmação explícita e geração de logs.

Importante: não publique CLIENT_ID, CLIENT_SECRET, arquivos
com dados reais de usuários ou outros dados sensíveis no repositório.

Funcionalidades

Script                          Finalidade                 Altera o Genesys?

01_exportar_filas_skills.py   Backup das filas e                Não
skills e geração
dos CSVs
normalizados

02_remover_filas_skills.py    Remove filas e                    Sim
skills existentes
com DRY RUN e
confirmação

03_adicionar_skills.py        Adiciona skills e                 Sim
ajusta proficiency
conforme
skills.csv

04_adicionar_filas.py         Adiciona usuários                 Sim
às filas conforme
filas.csv

05_adicionar_grupo.py         Adiciona usuários                 Sim
de usuarios.csv
ao grupo
configurado

Estrutura do projeto

genesys/
├── config.py
├── genesys_api.py
├── usuarios.csv
├── filas.csv
├── skills.csv
├── 01_exportar_filas_skills.py
├── 02_remover_filas_skills.py
├── 03_adicionar_skills.py
├── 04_adicionar_filas.py
├── 05_adicionar_grupo.py
├── consulta.py
└── output/

Execute os comandos a partir da pasta do projeto. Os exemplos utilizam o
launcher py do Windows.

Requisitos

Python 3

Biblioteca requests

OAuth Client configurado no Genesys Cloud com as permissões
necessárias

Instalação da dependência:

py -m pip install requests

Configuração

O arquivo config.py é o ponto central de configuração.

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

CLIENT_ID e CLIENT_SECRET devem pertencer ao mesmo ambiente definido
por LOGIN_URL e API_URL. Não misture credenciais e URLs de
organizações ou regiões diferentes.

Autenticação e genesys_api.py

Todos os scripts utilizam a classe compartilhada GenesysAPI.

from genesys_api import GenesysAPI

api = GenesysAPI()
api.autenticar()

dados = api.get("/api/v2/...")
dados = api.post("/api/v2/...", json={...})
dados = api.put("/api/v2/...", json={...})
dados = api.delete("/api/v2/...")

A autenticação usa OAuth Client Credentials:

POST {LOGIN_URL}/oauth/token
Authorization: Basic base64(CLIENT_ID:CLIENT_SECRET)
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials

A camada compartilhada contempla:

GET, POST, PUT e DELETE;

reautenticação em HTTP 401;

tratamento de HTTP 429 com Retry-After/backoff;

novas tentativas para erros transitórios 500, 502, 503 e
504;

paginação por get_all_pages() em endpoints que retornam
entities;

mensagens de exceção com método, URL, endpoint, HTTP e corpo da
resposta.

Arquivos CSV

usuarios.csv

Entrada dos scripts que processam uma lista de usuários.

email
usuario1@empresa.com
usuario2@empresa.com

O cabeçalho deve conter email.

filas.csv

email;user_id;fila;queue_id
usuario1@empresa.com;UUID_USUARIO;Nome da Fila;UUID_FILA

Cada linha representa uma associação entre usuário e fila. Em arquivos
montados manualmente, user_id e queue_id podem ficar vazios. O
script 04 consegue resolver o usuário pelo e-mail e a fila pelo nome.

skills.csv

email;user_id;skill;skill_id;proficiency
usuario1@empresa.com;UUID_USUARIO;Nome da Skill;UUID_SKILL;5

Cada linha representa uma associação entre usuário e skill.
proficiency deve estar entre 0 e 5.

No script 03, a skill é resolvida pelo nome no ambiente atual. O
skill_id presente no CSV funciona como referência/backup e pode ser
diferente entre ambientes.

01 - Exportar filas e skills

Registra o estado atual dos usuários antes das alterações.

py .\01_exportar_filas_skills.py

Arquivos gerados

output\backup_genesys_DATA_HORA.csv
output\filas_DATA_HORA.csv
output\skills_DATA_HORA.csv
filas.csv
skills.csv

Os arquivos normalizados retiram nome e ID do mesmo objeto retornado
pela API, evitando associações incorretas entre listas ordenadas
separadamente.

APIs utilizadas

Método                  Endpoint                                 Função

POST                    /api/v2/users/search                   Localiza o usuário
exatamente por
e-mail/username

GET                     /api/v2/users/{userId}/queues          Lista filas do usuário

02 - Remover filas e skills

Remove associações existentes com planejamento prévio e confirmação
posterior.

DRY RUN

py .\02_remover_filas_skills.py

Execução

py .\02_remover_filas_skills.py --execute

Confirmação:

REMOVER

Após cada alteração, o estado do usuário é consultado novamente. Uma
remoção só é registrada como REMOVIDA_CONFIRMADA quando o ID realmente
desaparece.

APIs utilizadas

Método                  Endpoint                                                 Função

GET                     /api/v2/users/{userId}/queues                          Consulta filas e
confirma remoção

GET                     /api/v2/users/{userId}/routingskills                   Consulta skills e
confirma remoção

DELETE                  /api/v2/users/{userId}/routingskills/{skillId}         Remove uma skill

POST                    /api/v2/routing/queues/{queueId}/members?delete=true   Remove usuário da fila

Body para remoção de membro da fila:

[
  {
    "id": "USER_ID"
  }
]

A documentação de origem registra que esta versão do script 02 lê o
backup resumido backup_genesys_*.csv. Uma evolução indicada é
fazê-lo consumir diretamente os backups normalizados.

03 - Adicionar skills

Aplica as associações descritas em skills.csv. O script resolve o
usuário por e-mail, localiza a skill pelo nome no ambiente atual e
adiciona ou atualiza a proficiency.

DRY RUN

py .\03_adicionar_skills.py

Execução

py .\03_adicionar_skills.py --execute

Confirmação:

ADICIONAR

APIs utilizadas

Método                  Endpoint                                           Função

POST                    /api/v2/users/search                             Resolve o usuário

GET                     /api/v2/routing/skills                           Procura a skill pelo
nome

GET                     /api/v2/routing/skills/{skillId}                 Consulta uma skill

GET                     /api/v2/users/{userId}/routingskills             Consulta e verifica
skills atuais

POST                    /api/v2/users/{userId}/routingskills             Adiciona uma skill

PUT                     /api/v2/users/{userId}/routingskills/{skillId}   Atualiza proficiency

Exemplo de body:

{
  "id": "SKILL_ID",
  "name": "NOME_DA_SKILL",
  "proficiency": 5
}

04 - Adicionar filas

Aplica as associações descritas em filas.csv.

O usuário é resolvido pelo e-mail. Para a fila, o script tenta primeiro
queue_id, quando informado, e utiliza o nome exato como alternativa.

DRY RUN

py .\04_adicionar_filas.py

Execução

py .\04_adicionar_filas.py --execute

Confirmação:

ADICIONAR

APIs utilizadas

Método                  Endpoint                                     Função

POST                    /api/v2/users/search                       Resolve o usuário

GET                     /api/v2/routing/queues                     Procura fila pelo nome

GET                     /api/v2/routing/queues/{queueId}           Valida/localiza fila
pelo ID

GET                     /api/v2/users/{userId}/queues              Consulta e confirma
filas

POST                    /api/v2/routing/queues/{queueId}/members   Adiciona usuário à fila

Body:

[
  {
    "id": "USER_ID"
  }
]

05 - Adicionar usuários ao grupo

Adiciona os usuários de usuarios.csv ao grupo definido em
GROUP_DESTINO.

Antes de alterar, o script consulta os membros atuais e ignora usuários
que já pertencem ao grupo.

DRY RUN

py .\05_adicionar_grupo.py

Execução

py .\05_adicionar_grupo.py --execute

Confirmação:

ADICIONAR

APIs utilizadas

Método                  Endpoint                             Função

POST                    /api/v2/users/search               Resolve o usuário

GET                     /api/v2/groups                     Localiza o grupo

GET                     /api/v2/groups/{groupId}/members   Lista membros e
confirma inclusão

POST                    /api/v2/groups/{groupId}/members   Adiciona membros

Body:

{
  "memberIds": [
    "USER_ID"
  ]
}

Enviar somente uma lista de strings causou HTTP 400 bad.request no
ambiente documentado.

Consulta de fila e skill

O consulta.py gera duas listas independentes:

todos os usuários da fila, tenham ou não a skill;

todos os usuários com a skill, estejam ou não na fila.

Usuários presentes nos dois conjuntos continuam aparecendo nos dois
CSVs.

py .\consulta.py

O script solicita o nome exato da fila e da skill.

Saída

output\fila_NOME_DA_FILA.csv
output\skill_NOME_DA_SKILL.csv

A interseção mostrada no terminal é apenas informativa.

APIs utilizadas

Método                  Endpoint                                     Função

GET                     /api/v2/routing/queues                     Localiza a fila

GET                     /api/v2/routing/skills                     Localiza a skill

GET                     /api/v2/routing/queues/{queueId}/members   Lista membros da fila

Fluxo operacional recomendado

01 Backup
   ↓
Revisar CSVs e backups
   ↓
02 DRY RUN → Remover associações
   ↓
03 DRY RUN → Aplicar skills
   ↓
04 DRY RUN → Aplicar filas
   ↓
05 DRY RUN → Aplicar grupo
   ↓
Consulta / validação

Etapa Ação               Comando

    1 Gerar backup       `py .\01_exportar_filas_skills.py`
    2 Revisar CSVs       Conferir `filas.csv`, `skills.csv` e backups
    3 Simular remoção    `py .\02_remover_filas_skills.py`
    4 Executar remoção   `py .\02_remover_filas_skills.py --execute`
    5 Simular skills     `py .\03_adicionar_skills.py`
    6 Aplicar skills     `py .\03_adicionar_skills.py --execute`
    7 Simular filas      `py .\04_adicionar_filas.py`
    8 Aplicar filas      `py .\04_adicionar_filas.py --execute`
    9 Simular grupo      `py .\05_adicionar_grupo.py`
   10 Aplicar grupo      `py .\05_adicionar_grupo.py --execute`
   11 Consultar          `py .\consulta.py`

DRY RUN, confirmações e logs

Script            Flag              Confirmação       Log

02                --execute       REMOVER         output\remocao_DATA_HORA.csv

03                --execute       ADICIONAR       output\adicao_skills_DATA_HORA.csv

04                --execute       ADICIONAR       output\adicao_filas_DATA_HORA.csv

05                --execute       ADICIONAR       output\adicao_grupo_DATA_HORA.csv

Sem --execute, os scripts de alteração montam o plano sem modificar o
Genesys Cloud.

Permissões do OAuth Client

O OAuth Client deve possuir as roles/permissões necessárias para os
recursos consultados ou alterados.

Se a autenticação funcionar, mas uma chamada retornar 403, verifique
as permissões relacionadas a:

Users;

Routing / Queues;

Routing Skills;

Groups.

Evite conceder permissões mais amplas do que o necessário.

Erros comuns

Sintoma                             Causa provável / ação

401 Unauthorized                  Token expirado, credencial inválida
ou região incorreta

403 Forbidden                     OAuth Client sem permissão para o
recurso

404                               ID inexistente no ambiente ou
associação/endpoint inválido

429 Too Many Requests             Rate limit; aguardar
Retry-After/backoff

400 bad.request no grupo          Usar {"memberIds":["USER_ID"]}

Fila não encontrada                 Verificar queue_id ou nome exato

Skill ID diferente entre ambientes  Resolver a skill pelo nome no
ambiente atual

Segurança

Nunca publique CLIENT_SECRET.

Mantenha config.py fora do controle de versão quando contiver
credenciais reais.

Execute o script 01 antes de alterações em lote.

Preserve os backups históricos em output.

Execute sempre o DRY RUN antes de --execute.

Confira região e API_URL antes de operações destrutivas.

Não edite IDs manualmente sem confirmar a qual ambiente pertencem.

Preserve logs para auditoria e diagnóstico.

Regenere imediatamente qualquer secret exposto.

.gitignore recomendado

# Credenciais
config.py
.env

# Dados operacionais
usuarios.csv
filas.csv
skills.csv
output/

# Python
__pycache__/
*.py[cod]
.venv/
venv/

# IDE / SO
.vscode/
.idea/
.DS_Store
Thumbs.db

Antes do primeiro git push, revise também o histórico do repositório
para garantir que nenhum secret tenha sido commitado anteriormente.

Referência rápida

# Backup
py .\01_exportar_filas_skills.py

# Remoção
py .\02_remover_filas_skills.py
py .\02_remover_filas_skills.py --execute

# Skills
py .\03_adicionar_skills.py
py .\03_adicionar_skills.py --execute

# Filas
py .\04_adicionar_filas.py
py .\04_adicionar_filas.py --execute

# Grupo
py .\05_adicionar_grupo.py
py .\05_adicionar_grupo.py --execute

# Consulta
py .\consulta.py

Referência técnica

A documentação operacional deste repositório foi construída a partir dos
scripts desenvolvidos e testados no projeto.

Para detalhes oficiais sobre endpoints, modelos, autenticação e
