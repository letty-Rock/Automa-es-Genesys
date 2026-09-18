import csv
import os
from datetime import datetime

from genesys_api import GenesysAPI
from config import USERS_FILE, OUTPUT_DIR

SEPARADOR_LISTA = "|"


def carregar_emails():
    if not os.path.exists(USERS_FILE):
        raise FileNotFoundError(f"Arquivo '{USERS_FILE}' não encontrado.")

    emails = []
    with open(USERS_FILE, "r", encoding="utf-8-sig", newline="") as arquivo:
        reader = csv.DictReader(arquivo)
        if not reader.fieldnames:
            raise ValueError("O arquivo CSV não possui cabeçalho.")

        colunas = {c.strip().lower(): c for c in reader.fieldnames}
        if "email" not in colunas:
            raise ValueError("O usuarios.csv precisa ter uma coluna chamada 'email'.")

        for linha in reader:
            email = (linha.get(colunas["email"]) or "").strip()
            if email:
                emails.append(email)

    return list(dict.fromkeys(emails))


def buscar_usuario(api, email):
    """Busca o usuário especificamente por email/username."""
    procurado = email.strip().lower()
    print(f"Procurando usuário: {email}")

    payload = {
        "pageSize": 100,
        "pageNumber": 1,
        "sortOrder": "ASC",
        "sortBy": "name",
        "query": [{
            "type": "EXACT",
            "fields": ["email", "username"],
            "values": [email]
        }]
    }

    resultado = api.post("/api/v2/users/search", json=payload)
    usuarios = resultado.get("results") or resultado.get("entities") or []
    print(f"Resultados da busca: {len(usuarios)}")

    for usuario in usuarios:
        username = (usuario.get("username") or "").strip().lower()
        user_email = (usuario.get("email") or "").strip().lower()
        if username == procurado or user_email == procurado:
            return usuario

    return None


def buscar_filas_usuario(api, user_id):
    return api.get_all_pages(
        f"/api/v2/users/{user_id}/queues",
        page_size=100
    )


def buscar_skills_usuario(api, user_id):
    return api.get_all_pages(
        f"/api/v2/users/{user_id}/routingskills",
        page_size=100
    )


def lista_nomes(objetos):
    nomes = [(x.get("name") or "").strip() for x in objetos]
    nomes = sorted(set(x for x in nomes if x), key=str.lower)
    return SEPARADOR_LISTA.join(nomes)


def lista_ids(objetos):
    ids = [(x.get("id") or "").strip() for x in objetos]
    return SEPARADOR_LISTA.join(dict.fromkeys(x for x in ids if x))


def lista_skills(skills):
    itens = []
    for skill in skills:
        nome = (skill.get("name") or "").strip()
        prof = skill.get("proficiency")
        if nome:
            itens.append(
                nome if prof in (None, "") else f"{nome}:{prof}"
            )
    return SEPARADOR_LISTA.join(
        sorted(set(itens), key=str.lower)
    )


def salvar_csv(caminho, campos, registros):
    with open(
        caminho,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as arquivo:
        writer = csv.DictWriter(
            arquivo,
            fieldnames=campos,
            delimiter=";"
        )
        writer.writeheader()
        writer.writerows(registros)


def main():
    print("=" * 70)
    print("GENESYS CLOUD - BACKUP DE FILAS E SKILLS")
    print("=" * 70)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    emails = carregar_emails()
    print(f"\nUsuários no CSV: {len(emails)}")

    if not emails:
        return

    api = GenesysAPI()
    api.autenticar()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    arquivo_backup = os.path.join(
        OUTPUT_DIR,
        f"backup_genesys_{timestamp}.csv"
    )

    arquivo_filas_backup = os.path.join(
        OUTPUT_DIR,
        f"filas_{timestamp}.csv"
    )

    arquivo_skills_backup = os.path.join(
        OUTPUT_DIR,
        f"skills_{timestamp}.csv"
    )

    # Arquivos de trabalho consumidos diretamente pelos scripts 03 e 04.
    arquivo_filas = "filas.csv"
    arquivo_skills = "skills.csv"

    backup = []
    filas_normalizadas = []
    skills_normalizadas = []

    for numero, email in enumerate(emails, 1):
        print("\n" + "-" * 70)
        print(f"[{numero}/{len(emails)}] {email}")
        print("-" * 70)

        try:
            usuario = buscar_usuario(api, email)

            if not usuario:
                print("USUÁRIO NÃO ENCONTRADO")
                backup.append({
                    "email": email,
                    "user_id": "",
                    "nome": "",
                    "status": "NAO_ENCONTRADO",
                    "filas": "",
                    "filas_ids": "",
                    "skills": "",
                    "skills_ids": ""
                })
                continue

            user_id = usuario.get("id", "")
            nome = usuario.get("name", "")
            user_email = usuario.get("email", "") or email

            print(f"Nome: {nome}")
            print(f"ID:   {user_id}")

            filas = buscar_filas_usuario(api, user_id)
            skills = buscar_skills_usuario(api, user_id)

            print(f"Filas encontradas:  {len(filas)}")
            print(f"Skills encontradas: {len(skills)}")

            # --------------------------------------------------------
            # Backup resumido original - mantido
            # --------------------------------------------------------
            backup.append({
                "email": user_email,
                "user_id": user_id,
                "nome": nome,
                "status": "OK",
                "filas": lista_nomes(filas),
                "filas_ids": lista_ids(filas),
                "skills": lista_skills(skills),
                "skills_ids": lista_ids(skills)
            })

            # --------------------------------------------------------
            # FILAS NORMALIZADAS
            # Uma linha = um usuário + uma fila.
            #
            # IMPORTANTE:
            # nome e ID são retirados do MESMO objeto retornado pela API.
            # Não existe pareamento por posição entre listas.
            # --------------------------------------------------------
            for fila in filas:
                queue_id = (fila.get("id") or "").strip()
                queue_name = (fila.get("name") or "").strip()

                if not queue_id and not queue_name:
                    continue

                filas_normalizadas.append({
                    "email": user_email,
                    "user_id": user_id,
                    "fila": queue_name,
                    "queue_id": queue_id,
                })

            # --------------------------------------------------------
            # SKILLS NORMALIZADAS
            # Uma linha = um usuário + uma skill + proficiency.
            #
            # nome, ID e proficiency são retirados do MESMO objeto.
            # --------------------------------------------------------
            for skill in skills:
                skill_id = (skill.get("id") or "").strip()
                skill_name = (skill.get("name") or "").strip()
                proficiency = skill.get("proficiency")

                if not skill_id and not skill_name:
                    continue

                skills_normalizadas.append({
                    "email": user_email,
                    "user_id": user_id,
                    "skill": skill_name,
                    "skill_id": skill_id,
                    "proficiency": (
                        ""
                        if proficiency is None
                        else proficiency
                    ),
                })

        except Exception as erro:
            print(f"ERRO: {erro}")
            backup.append({
                "email": email,
                "user_id": "",
                "nome": "",
                "status": f"ERRO: {erro}",
                "filas": "",
                "filas_ids": "",
                "skills": "",
                "skills_ids": ""
            })

    # ------------------------------------------------------------
    # 1) BACKUP RESUMIDO ORIGINAL
    # ------------------------------------------------------------
    campos_backup = [
        "email",
        "user_id",
        "nome",
        "status",
        "filas",
        "filas_ids",
        "skills",
        "skills_ids"
    ]

    salvar_csv(
        arquivo_backup,
        campos_backup,
        backup
    )

    # ------------------------------------------------------------
    # 2) FILAS - formato aceito pelo 04
    # ------------------------------------------------------------
    campos_filas = [
        "email",
        "user_id",
        "fila",
        "queue_id"
    ]

    salvar_csv(
        arquivo_filas_backup,
        campos_filas,
        filas_normalizadas
    )

    salvar_csv(
        arquivo_filas,
        campos_filas,
        filas_normalizadas
    )

    # ------------------------------------------------------------
    # 3) SKILLS - formato aceito pelo 03
    # ------------------------------------------------------------
    campos_skills = [
        "email",
        "user_id",
        "skill",
        "skill_id",
        "proficiency"
    ]

    salvar_csv(
        arquivo_skills_backup,
        campos_skills,
        skills_normalizadas
    )

    salvar_csv(
        arquivo_skills,
        campos_skills,
        skills_normalizadas
    )

    encontrados = sum(
        x["status"] == "OK"
        for x in backup
    )
    nao_encontrados = sum(
        x["status"] == "NAO_ENCONTRADO"
        for x in backup
    )
    erros = len(backup) - encontrados - nao_encontrados

    print("\n" + "=" * 70)
    print("BACKUP FINALIZADO")
    print("=" * 70)
    print(f"Usuários processados: {len(emails)}")
    print(f"Encontrados:           {encontrados}")
    print(f"Não encontrados:       {nao_encontrados}")
    print(f"Erros:                 {erros}")
    print(f"Associações de filas:  {len(filas_normalizadas)}")
    print(f"Associações de skills: {len(skills_normalizadas)}")
    print()
    print(f"Backup geral:           {arquivo_backup}")
    print(f"Backup filas:           {arquivo_filas_backup}")
    print(f"Backup skills:          {arquivo_skills_backup}")
    print(f"Arquivo para o 04:      {arquivo_filas}")
    print(f"Arquivo para o 03:      {arquivo_skills}")
    print()
    print("Nenhuma alteração foi realizada no Genesys Cloud.")


if __name__ == "__main__":
    main()
