import csv
import json
import os
import re
import sys
from collections import Counter

from genesys_api import GenesysAPI
from config import OUTPUT_DIR

PAGE_SIZE = 100


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

    raise ValueError(f'Fila "{nome}" não encontrada.')


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

    raise ValueError(f'Skill "{nome}" não encontrada.')


def nome_seguro(texto):
    texto = re.sub(r'[<>:"/\\|?*]+', "_", texto.strip())
    texto = re.sub(r"\s+", "_", texto)
    return texto or "resultado"


def coletar_membros_fila(api, queue_id):
    """
    Coleta TODOS os registros brutos do endpoint de membros da fila.
    Não deduplica nada.
    """
    registros = []
    pagina = 1

    while True:
        dados = api.get(
            f"/api/v2/routing/queues/{queue_id}/members",
            params={
                "pageSize": PAGE_SIZE,
                "pageNumber": pagina,
            },
        )

        entidades = dados.get("entities") or []

        print(
            f"  Página {pagina}: "
            f"{len(entidades)} registro(s)"
        )

        if not entidades:
            break

        for indice, membro in enumerate(entidades, 1):
            user = membro.get("user") or {}

            membro_id = str(
                membro.get("id") or ""
            ).strip()

            user_id = str(
                user.get("id") or ""
            ).strip()

            id_extraido = (
                user_id
                or membro_id
            )

            email = str(
                user.get("email")
                or membro.get("email")
                or ""
            ).strip()

            nome = str(
                user.get("name")
                or membro.get("name")
                or ""
            ).strip()

            registros.append({
                "pagina": pagina,
                "indice_pagina": indice,
                "membro_id": membro_id,
                "user_id": user_id,
                "id_extraido": id_extraido,
                "email": email,
                "nome": nome,
                "joined": membro.get("joined", ""),
                "ring_number": membro.get("ringNumber", ""),
                "routing_status": json.dumps(
                    membro.get("routingStatus"),
                    ensure_ascii=False,
                    default=str,
                )
                if membro.get("routingStatus") is not None
                else "",
                "campos_membro": ",".join(
                    sorted(membro.keys())
                ),
                "campos_user": ",".join(
                    sorted(user.keys())
                ),
                "json_membro": json.dumps(
                    membro,
                    ensure_ascii=False,
                    default=str,
                ),
            })

        # Para este endpoint, não dependemos de pageCount.
        if len(entidades) < PAGE_SIZE:
            break

        pagina += 1

    return registros


def salvar_diagnosticos_fila(registros, fila_nome):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    base = nome_seguro(fila_nome)

    arquivo_todos = os.path.abspath(
        os.path.join(
            OUTPUT_DIR,
            f"diagnostico_membros_fila_{base}.csv",
        )
    )

    arquivo_repetidos = os.path.abspath(
        os.path.join(
            OUTPUT_DIR,
            f"diagnostico_ids_repetidos_{base}.csv",
        )
    )

    campos = [
        "pagina",
        "indice_pagina",
        "membro_id",
        "user_id",
        "id_extraido",
        "email",
        "nome",
        "joined",
        "ring_number",
        "routing_status",
        "campos_membro",
        "campos_user",
        "json_membro",
    ]

    with open(
        arquivo_todos,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as arquivo:
        writer = csv.DictWriter(
            arquivo,
            fieldnames=campos,
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(registros)

    contagem = Counter(
        item["id_extraido"]
        for item in registros
        if item["id_extraido"]
    )

    ids_repetidos = {
        item_id
        for item_id, quantidade in contagem.items()
        if quantidade > 1
    }

    repetidos = [
        item
        for item in registros
        if item["id_extraido"] in ids_repetidos
    ]

    with open(
        arquivo_repetidos,
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as arquivo:
        writer = csv.DictWriter(
            arquivo,
            fieldnames=campos,
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(repetidos)

    sem_id = sum(
        1 for item in registros
        if not item["id_extraido"]
    )

    sem_email = sum(
        1 for item in registros
        if not item["email"]
    )

    print()
    print("=" * 75)
    print("DIAGNÓSTICO DA FILA")
    print("=" * 75)
    print(
        f"Registros brutos retornados:    "
        f"{len(registros)}"
    )
    print(
        f"IDs únicos encontrados:         "
        f"{len(contagem)}"
    )
    print(
        f"IDs que aparecem repetidos:     "
        f"{len(ids_repetidos)}"
    )
    print(
        f"Registros envolvidos em repetição: "
        f"{len(repetidos)}"
    )
    print(
        f"Registros sem ID:               "
        f"{sem_id}"
    )
    print(
        f"Registros sem e-mail:           "
        f"{sem_email}"
    )

    print()
    print("ARQUIVOS DE DIAGNÓSTICO")
    print("-" * 75)
    print(f"Todos os registros: {arquivo_todos}")
    print(f"Somente repetidos : {arquivo_repetidos}")

    return arquivo_todos, arquivo_repetidos


def usuarios_unicos_da_fila(registros):
    """
    Mantido apenas para a conferência atual.
    O diagnóstico bruto já foi salvo antes desta deduplicação.
    """
    usuarios = {}

    for item in registros:
        user_id = item["id_extraido"]

        if not user_id:
            continue

        usuarios[user_id] = {
            "email": item["email"],
            "nome": item["nome"],
        }

    return usuarios


def usuarios_com_skill(api, skill):
    usuarios = {}
    pagina = 1
    nome_skill = skill["name"]

    while True:
        payload = {
            "sortOrder": "ASC",
            "sortBy": "name",
            "pageSize": PAGE_SIZE,
            "pageNumber": pagina,
            "expand": ["skills"],
            "query": [
                {
                    "values": ["active"],
                    "fields": ["state"],
                    "type": "EXACT",
                },
                {
                    "values": [nome_skill],
                    "fields": ["routingSkills"],
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
            user_id = str(
                user.get("id") or ""
            ).strip()

            if not user_id:
                continue

            usuarios[user_id] = {
                "email": str(
                    user.get("email") or ""
                ).strip(),
                "nome": str(
                    user.get("name") or ""
                ).strip(),
            }

        page_count = dados.get("pageCount")
        total = dados.get("total")

        if page_count is not None:
            if pagina >= int(page_count):
                break
        elif total is not None:
            if pagina * PAGE_SIZE >= int(total):
                break
        elif len(itens) < PAGE_SIZE:
            break

        pagina += 1

    return usuarios


def salvar_usuarios(caminho, usuarios):
    os.makedirs(
        os.path.dirname(caminho) or ".",
        exist_ok=True,
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

        for user_id, item in sorted(
            usuarios.items(),
            key=lambda x: (
                x[1].get("email")
                or x[1].get("nome")
                or x[0]
            ).casefold(),
        ):
            writer.writerow({
                "email": item.get("email") or "",
                "nome": item.get("nome") or "",
                "user_id": user_id,
            })


def main():
    print("=" * 75)
    print("GENESYS CLOUD - DIAGNÓSTICO FILA E SKILL")
    print("SOMENTE LEITURA")
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

    api = GenesysAPI()
    api.autenticar()

    print("\nLocalizando fila...")
    fila = localizar_fila(
        api,
        fila_nome,
    )

    print(
        f"Fila encontrada: "
        f"{fila['name']} ({fila['id']})"
    )

    print("\nLocalizando skill...")
    skill = buscar_skill(
        api,
        skill_nome,
    )

    print(
        f"Skill encontrada: "
        f"{skill['name']} ({skill['id']})"
    )

    print()
    print("Coletando TODOS os registros brutos da fila...")

    registros_fila = coletar_membros_fila(
        api,
        fila["id"],
    )

    salvar_diagnosticos_fila(
        registros_fila,
        fila["name"],
    )

    usuarios_fila = usuarios_unicos_da_fila(
        registros_fila
    )

    print()
    print("Buscando usuários com a skill...")

    usuarios_skill = usuarios_com_skill(
        api,
        skill,
    )

    ids_ambos = (
        set(usuarios_fila)
        & set(usuarios_skill)
    )

    print()
    print("=" * 75)
    print("CONFERÊNCIA")
    print("=" * 75)

    print(
        f"Registros brutos da fila:       "
        f"{len(registros_fila)}"
    )

    print(
        f"IDs únicos extraídos da fila:   "
        f"{len(usuarios_fila)}"
    )

    print(
        f"Usuários únicos com a skill:    "
        f"{len(usuarios_skill)}"
    )

    print(
        f"IDs presentes nos dois:         "
        f"{len(ids_ambos)}"
    )

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True,
    )

    arquivo_skill = os.path.abspath(
        os.path.join(
            OUTPUT_DIR,
            f"skill_{nome_seguro(skill['name'])}.csv",
        )
    )

    salvar_usuarios(
        arquivo_skill,
        usuarios_skill,
    )

    print()
    print("=" * 75)
    print("FINALIZADO")
    print("=" * 75)
    print(
        "O diagnóstico preservou todos os "
        "registros brutos da fila antes "
        "de qualquer deduplicação."
    )
    print(f"Skill: {arquivo_skill}")


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        print("\nExecução cancelada.")

    except Exception as erro:
        print(f"\nERRO: {erro}")
        sys.exit(1)
