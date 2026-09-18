import os

# ============================================================
# GENESYS CLOUD
# ============================================================

REGION = "mypurecloud.com"

LOGIN_URL = f"https://login.{REGION}"
API_URL = f"https://api.{REGION}"

# Credenciais são lidas das variáveis de ambiente.
# NÃO coloque Client ID / Client Secret diretamente neste arquivo.

CLIENT_ID = ("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
CLIENT_SECRET = ("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")


# ============================================================
# ARQUIVOS
# ============================================================

USERS_FILE = "usuarios.csv"
OUTPUT_DIR = "output"


# ============================================================
# DESTINOS
# ============================================================

QUEUE_DESTINO = "filas.csv"
SKILL_DESTINO = "skills.csv"

# Vamos preencher quando chegarmos no script de grupos.
GROUP_DESTINO = ""


# ============================================================
# EXECUÇÃO
# ============================================================

# Pausa entre chamadas para reduzir risco de rate limit.
REQUEST_DELAY = 0.15

# Quantidade máxima de tentativas em caso de erro temporário/429.
MAX_RETRIES = 5

# ============================================================
# PROTEÇÃO CONTRA REMOÇÃO
# ============================================================

# Filas que o 02_remover_filas_skills.py NUNCA deve remover.
# Informe o nome exato da fila.
FILAS_PROTEGIDAS = [
    # "TESTE",
    # "TESTE2"
]


# Skills que o 02_remover_filas_skills.py NUNCA deve remover.
# Informe o nome exato da skill.
SKILLS_PROTEGIDAS = [
    #"AtendimentoTESTE",
    # "Skill Principal",
]