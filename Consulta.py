import csv
import os
import re
import sys

from genesys_api import GenesysAPI
from config import OUTPUT_DIR


PAGE_SIZE = 100


# ============================================================
# LOCALIZAR FILA
# ============================================================

def localizar_fila(api, nome):
    pagina = 1

    while True:
        dados = api.get(
            "/api/v2/routing/queues",
            params={
                "name": nome,
                "pageSize": PAGE_SIZE,
                "pageNumber": pagina,
            },
        )

        entidades = dados.get("entities") or []

        for fila in entidades:
            if (
                (fila.get("name") or "").strip().casefold()
                == nome.strip().casefold()
            ):
                return fila

        page_count = dados.get("pageCount")

        if page_count is not None:
            if pagina >= int(page_count):
                break

        elif len(entidades) < PAGE_SIZE:
            break

        pagina += 1

    raise ValueError(
        f'Fila "{nome}" não encontrada.'
    )


# ============================================================
# LOCALIZAR SKILL
# ============================================================

def buscar_skill(api, nome):
    pagina = 1

    while True:
        dados = api.get(
            "/api/v2/routing/skills",
            params={
                "pageSize": PAGE_SIZE,
                "pageNumber": pagina,
                "name": nome,
            },
        )

        entidades = dados.get("entities") or []

        for skill in entidades:
            if (
                (skill.get("name") or "").strip().casefold()
                == nome.strip().casefold()
            ):
                return skill

        page_count = dados.get("pageCount")

        if page_count is not None:
            if pagina >= int(page_count):
                break

        elif len(entidades) < PAGE_SIZE:
            break

        pagina += 1

    raise ValueError(
        f'Skill "{nome}" não encontrada.'
    )


# ============================================================
# MEMBROS DA FILA
# ============================================================

def membros_da_fila(api, queue_id):
    """
    Retorna TODOS os usuários associados à fila.

    IMPORTANTE:
    A consulta da fila é completamente independente
    da consulta de skill.

    Neste endpoint não dependemos de pageCount para
    determinar o final da paginação.
    """

    usuarios = {}

    pagina = 1
    total_bruto = 0

    while True:

        dados = api.get(
            f"/api/v2/routing/queues/{queue_id}/members",
            params={
                "pageSize": PAGE_SIZE,
                "pageNumber": pagina,
            },
        )

        entidades = dados.get("entities") or []

        quantidade = len(entidades)

        total_bruto += quantidade

        print(
            f"  Página {pagina}: "
            f"{quantidade} membro(s)"
        )

        # Nenhum registro retornado.
        if not entidades:
            break

        for membro in entidades:

            # Dependendo da resposta da API,
            # os dados podem estar diretamente
            # no membro ou dentro de "user".
            user = membro.get("user") or {}

            user_id = (
                user.get("id")
                or membro.get("id")
                or ""
            )

            email = (
                user.get("email")
                or membro.get("email")
                or ""
            ).strip()

            nome = (
                user.get("name")
                or membro.get("name")
                or ""
            ).strip()

            if user_id:

                usuarios[user_id] = {
                    "email": email,
                    "nome": nome,
                }

        # ====================================================
        # PAGINAÇÃO
        # ====================================================
        #
        # Não usamos:
        #
        # pageCount = dados.get("pageCount") or 1
        #
        # porque esse endpoint pode não retornar pageCount.
        #
        # Se vierem menos de 100 registros, chegamos
        # à última página.
        # ====================================================

        if quantidade < PAGE_SIZE:
            break

        pagina += 1

    # ========================================================
    # DIAGNÓSTICO
    # ========================================================

    total_com_email = sum(
        1
        for usuario in usuarios.values()
        if usuario.get("email")
    )

    total_sem_email = (
        len(usuarios)
        - total_com_email
    )

    print()
    print("-" * 75)
    print("RESULTADO DA CONSULTA DA FILA")
    print("-" * 75)

    print(
        f"Total bruto retornado pela API: "
        f"{total_bruto}"
    )

    print(
        f"IDs únicos encontrados:         "
        f"{len(usuarios)}"
    )

    print(
        f"Membros com e-mail:             "
        f"{total_com_email}"
    )

    print(
        f"Membros sem e-mail:             "
        f"{total_sem_email}"
    )

    return usuarios


# ============================================================
# USUÁRIOS COM SKILL
# ============================================================

def usuarios_com_skill(api, skill):
    """
    Retorna TODOS os usuários ativos que possuem a skill.

    Esta consulta é completamente independente da fila.

    Portanto:

    - usuário somente na fila -> aparece no arquivo da fila
    - usuário somente na skill -> aparece no arquivo da skill
    - usuário nos dois -> aparece nos dois arquivos
    """

    usuarios = {}

    pagina = 1

    nome_skill = skill["name"]

    while True:

        payload = {
            "sortOrder": "ASC",
            "sortBy": "name",
            "pageSize": PAGE_SIZE,
            "pageNumber": pagina,
            "expand": [
                "skills"
            ],
            "query": [
                {
                    "values": [
                        "active"
                    ],
                    "fields": [
                        "state"
                    ],
                    "type": "EXACT",
                },
                {
                    "values": [
                        nome_skill
                    ],
                    "fields": [
                        "routingSkills"
                    ],
                    "type": "EXACT",
                },
            ],
        }

        dados = api.post(
            "/api/v2/users/search",
            json=payload,
        )

        itens = (
            dados.get("results")
            or dados.get("entities")
            or []
        )

        print(
            f"  Página {pagina}: "
            f"{len(itens)} usuário(s)"
        )

        for user in itens:

            user_id = (
                user.get("id")
                or ""
            )

            email = (
                user.get("email")
                or ""
            ).strip()

            nome = (
                user.get("name")
                or ""
            ).strip()

            if user_id:

                usuarios[user_id] = {
                    "email": email,
                    "nome": nome,
                }

        # ====================================================
        # PAGINAÇÃO DA PESQUISA DE USUÁRIOS
        # ====================================================

        page_count = dados.get(
            "pageCount"
        )

        total = dados.get(
            "total"
        )

        if page_count is not None:

            if pagina >= int(page_count):
                break

        elif total is not None:

            if (
                pagina * PAGE_SIZE
                >= int(total)
            ):
                break

        elif len(itens) < PAGE_SIZE:

            break

        pagina += 1

    print()
    print("-" * 75)
    print("RESULTADO DA CONSULTA DA SKILL")
    print("-" * 75)

    print(
        f"Usuários únicos com a skill: "
        f"{len(usuarios)}"
    )

    return usuarios


# ============================================================
# NOME SEGURO PARA ARQUIVO
# ============================================================

def nome_seguro(texto):

    texto = re.sub(
        r'[<>:"/\\|?*]+',
        "_",
        texto.strip(),
    )

    texto = re.sub(
        r"\s+",
        "_",
        texto,
    )

    return texto or "resultado"


# ============================================================
# SALVAR CSV
# ============================================================

def salvar_csv(caminho, usuarios):
    """
    Salva TODOS os usuários encontrados.

    Diferente da versão anterior, um membro sem e-mail
    não é simplesmente descartado.

    O CSV contém:

    email
    nome
    user_id

    Dessa forma conseguimos comparar exatamente o número
    de membros retornado pelo Genesys.
    """

    registros = []

    for user_id, usuario in usuarios.items():

        registros.append({
            "email": (
                usuario.get("email")
                or ""
            ),
            "nome": (
                usuario.get("nome")
                or ""
            ),
            "user_id": user_id,
        })

    registros.sort(
        key=lambda item: (
            item["email"]
            or item["nome"]
            or item["user_id"]
        ).casefold()
    )

    with open(
        caminho,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as arquivo:

        writer = csv.DictWriter(
            arquivo,
            fieldnames=[
                "email",
                "nome",
                "user_id",
            ],
            delimiter=";",
        )

        writer.writeheader()

        writer.writerows(
            registros
        )


# ============================================================
# MOSTRAR RESULTADOS
# ============================================================

def mostrar(titulo, usuarios):

    print()
    print("=" * 75)
    print(titulo)
    print("=" * 75)

    registros = sorted(
        usuarios.items(),
        key=lambda item: (
            item[1].get("email")
            or item[1].get("nome")
            or item[0]
        ).casefold(),
    )

    for numero, (
        user_id,
        usuario,
    ) in enumerate(
        registros,
        1,
    ):

        email = (
            usuario.get("email")
            or "[SEM E-MAIL]"
        )

        nome = (
            usuario.get("nome")
            or ""
        )

        if nome:

            print(
                f"{numero:>4}. "
                f"{email} | "
                f"{nome}"
            )

        else:

            print(
                f"{numero:>4}. "
                f"{email} | "
                f"{user_id}"
            )

    if not registros:

        print(
            "Nenhum usuário encontrado."
        )

    print(
        f"\nTOTAL: {len(registros)}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 75)
    print(
        "GENESYS CLOUD - CONSULTA FILA E SKILL"
    )
    print(
        "SOMENTE LEITURA"
    )
    print("=" * 75)

    fila_nome = input(
        "\nNome EXATO da fila: "
    ).strip()

    skill_nome = input(
        "Nome EXATO da skill: "
    ).strip()

    if not fila_nome or not skill_nome:

        raise ValueError(
            "Informe a fila e a skill."
        )

    # ========================================================
    # AUTENTICAÇÃO
    # ========================================================

    api = GenesysAPI()

    api.autenticar()

    # ========================================================
    # FILA
    # ========================================================

    print(
        "\nLocalizando fila..."
    )

    fila = localizar_fila(
        api,
        fila_nome,
    )

    print(
        f"Fila encontrada: "
        f"{fila['name']} "
        f"({fila['id']})"
    )

    # ========================================================
    # SKILL
    # ========================================================

    print(
        "\nLocalizando skill..."
    )

    skill = buscar_skill(
        api,
        skill_nome,
    )

    print(
        f"Skill encontrada: "
        f"{skill['name']} "
        f"({skill['id']})"
    )

    # ========================================================
    # CONSULTAR FILA
    # ========================================================

    print()
    print(
        "Buscando TODOS os membros da fila..."
    )

    usuarios_fila = membros_da_fila(
        api,
        fila["id"],
    )

    # ========================================================
    # CONSULTAR SKILL
    # ========================================================

    print()
    print(
        "Buscando TODOS os usuários com a skill..."
    )

    usuarios_skill = usuarios_com_skill(
        api,
        skill,
    )

    # ========================================================
    # MOSTRAR FILA
    # ========================================================

    mostrar(
        (
            f'MEMBROS DA FILA: '
            f'{fila["name"]}'
        ),
        usuarios_fila,
    )

    # ========================================================
    # MOSTRAR SKILL
    # ========================================================

    mostrar(
        (
            f'USUÁRIOS COM A SKILL: '
            f'{skill["name"]}'
        ),
        usuarios_skill,
    )

    # ========================================================
    # CONFERÊNCIA
    # ========================================================

    ids_fila = set(
        usuarios_fila
    )

    ids_skill = set(
        usuarios_skill
    )

    ids_ambos = (
        ids_fila
        & ids_skill
    )

    somente_fila = (
        ids_fila
        - ids_skill
    )

    somente_skill = (
        ids_skill
        - ids_fila
    )

    print()
    print("=" * 75)
    print("CONFERÊNCIA")
    print("=" * 75)

    print(
        f"Membros únicos na fila:       "
        f"{len(ids_fila)}"
    )

    print(
        f"Usuários únicos com a skill:  "
        f"{len(ids_skill)}"
    )

    print(
        f"Presentes nos dois:           "
        f"{len(ids_ambos)}"
    )

    print(
        f"Somente na fila:              "
        f"{len(somente_fila)}"
    )

    print(
        f"Somente com a skill:          "
        f"{len(somente_skill)}"
    )

    # ========================================================
    # ARQUIVOS
    # ========================================================

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True,
    )

    arquivo_fila = os.path.join(
        OUTPUT_DIR,
        (
            f"fila_"
            f"{nome_seguro(fila['name'])}"
            f".csv"
        ),
    )

    arquivo_skill = os.path.join(
        OUTPUT_DIR,
        (
            f"skill_"
            f"{nome_seguro(skill['name'])}"
            f".csv"
        ),
    )

    # ========================================================
    # SALVAR
    # ========================================================

    salvar_csv(
        arquivo_fila,
        usuarios_fila,
    )

    salvar_csv(
        arquivo_skill,
        usuarios_skill,
    )

    # ========================================================
    # FINAL
    # ========================================================

    print()
    print("=" * 75)
    print("ARQUIVOS CSV CRIADOS")
    print("=" * 75)

    print(
        f"Fila : {arquivo_fila}"
    )

    print(
        f"Skill: {arquivo_skill}"
    )

    print()

    print(
        f"Membros encontrados na fila : "
        f"{len(usuarios_fila)}"
    )

    print(
        f"Usuários encontrados na skill: "
        f"{len(usuarios_skill)}"
    )

    print()

    print(
        "IMPORTANTE:"
    )

    print(
        "A fila e a skill são consultadas "
        "de forma independente."
    )

    print(
        "Um usuário presente nos dois "
        "continua aparecendo nos dois arquivos."
    )


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print(
            "\nExecução cancelada."
        )

    except Exception as erro:

        print(
            f"\nERRO: {erro}"
        )

        sys.exit(1)