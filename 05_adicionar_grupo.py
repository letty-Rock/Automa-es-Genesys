import argparse
import csv
import os
import time
from datetime import datetime

from genesys_api import GenesysAPI
from config import USERS_FILE, OUTPUT_DIR, GROUP_DESTINO


def carregar_emails():
    if not os.path.exists(USERS_FILE):
        raise FileNotFoundError(
            f"Arquivo '{USERS_FILE}' não encontrado."
        )

    with open(
        USERS_FILE,
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as arquivo:
        reader = csv.DictReader(arquivo)

        if not reader.fieldnames:
            raise ValueError("O arquivo CSV não possui cabeçalho.")

        colunas = {
            coluna.strip().lower(): coluna
            for coluna in reader.fieldnames
        }

        if "email" not in colunas:
            raise ValueError(
                "O usuarios.csv precisa ter uma coluna chamada 'email'."
            )

        emails = []

        for linha in reader:
            email = (
                linha.get(colunas["email"]) or ""
            ).strip()

            if email:
                emails.append(email)

    return list(dict.fromkeys(emails))


def buscar_usuario(api, email):
    payload = {
        "pageSize": 100,
        "pageNumber": 1,
        "sortOrder": "ASC",
        "sortBy": "name",
        "query": [{
            "type": "EXACT",
            "fields": ["email", "username"],
            "values": [email],
        }],
    }

    dados = api.post(
        "/api/v2/users/search",
        json=payload,
    )

    for usuario in (
        dados.get("results")
        or dados.get("entities")
        or []
    ):
        email_api = (
            usuario.get("email") or ""
        ).strip().lower()

        username_api = (
            usuario.get("username") or ""
        ).strip().lower()

        if email.lower() in (
            email_api,
            username_api,
        ):
            return usuario

    return None


def buscar_grupo(api):
    grupos = api.get_all_pages(
        "/api/v2/groups"
    )

    encontrados = [
        grupo
        for grupo in grupos
        if (grupo.get("name") or "").strip().lower()
        == GROUP_DESTINO.strip().lower()
    ]

    if not encontrados:
        raise RuntimeError(
            f"Grupo '{GROUP_DESTINO}' não encontrado."
        )

    if len(encontrados) > 1:
        raise RuntimeError(
            f"Mais de um grupo chamado "
            f"'{GROUP_DESTINO}' encontrado."
        )

    return encontrados[0]


def membros_grupo(api, group_id):
    """
    Retorna os membros atuais do grupo.
    """
    return api.get_all_pages(
        f"/api/v2/groups/{group_id}/members"
    )


def existe_membro(membros, user_id):
    return any(
        str(membro.get("id")) == str(user_id)
        for membro in membros
    )


def confirmar(api, group_id, user_id):
    for tentativa in range(4):
        atuais = membros_grupo(
            api,
            group_id,
        )

        if existe_membro(atuais, user_id):
            return True

        if tentativa < 3:
            time.sleep(2)

    return False


def main():
    parser = argparse.ArgumentParser(
        description=(
            "05 - Adiciona usuários do usuarios.csv "
            "ao GROUP_DESTINO."
        )
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Executa as alterações. Sem isso, apenas DRY RUN.",
    )
    args = parser.parse_args()

    if not GROUP_DESTINO:
        raise RuntimeError(
            "Defina GROUP_DESTINO no config.py."
        )

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True,
    )

    emails = carregar_emails()

    api = GenesysAPI()
    api.autenticar()

    grupo = buscar_grupo(api)
    group_id = grupo["id"]
    group_name = grupo["name"]

    print("=" * 76)
    print("05 - ADICIONAR USUÁRIOS AO GRUPO")
    print("=" * 76)
    print(f"Grupo:             {group_name}")
    print(f"ID:                {group_id}")
    print(f"Usuários no CSV:   {len(emails)}")
    print("Modo:", "EXECUÇÃO" if args.execute else "DRY RUN")
    print()

    # Busca uma vez os membros atuais para montar o plano.
    membros_atuais = membros_grupo(
        api,
        group_id,
    )

    usuarios_cache = {}
    plano = []
    erros_plano = []
    ja_membros = 0

    for numero, email in enumerate(emails, start=1):
        print(
            f"[{numero}/{len(emails)}] {email}"
        )

        chave_email = email.lower()

        if chave_email not in usuarios_cache:
            usuarios_cache[chave_email] = buscar_usuario(
                api,
                email,
            )

        usuario = usuarios_cache[chave_email]

        if not usuario:
            detalhe = "USUÁRIO NÃO ENCONTRADO"
            print(f"  {detalhe}")

            erros_plano.append({
                "email": email,
                "user_id": "",
                "grupo": group_name,
                "group_id": group_id,
                "tipo_erro": detalhe,
            })
            continue

        user_id = usuario["id"]

        if existe_membro(
            membros_atuais,
            user_id,
        ):
            ja_membros += 1
            print("  JÁ ESTÁ NO GRUPO.")
            continue

        print(f"  AÇÃO: ADICIONAR AO GRUPO {group_name}")

        plano.append({
            "email": email,
            "user_id": user_id,
            "grupo": group_name,
            "group_id": group_id,
        })

    print("\n" + "=" * 76)
    print("RESUMO")
    print("=" * 76)
    print(f"Usuários a adicionar:            {len(plano)}")
    print(f"Usuários que já estão no grupo:  {ja_membros}")
    print(f"Registros com erro no plano:     {len(erros_plano)}")
    print(f"Total de alterações planejadas:  {len(plano)}")

    if not args.execute:
        print("\nDRY RUN: nenhuma alteração foi realizada.")
        print(
            r"Para executar: "
            r"py .\05_adicionar_grupo.py --execute"
        )
        return

    if not plano:
        print("\nNada para adicionar.")
        return

    confirmacao = input(
        "\nDigite ADICIONAR para continuar: "
    ).strip()

    if confirmacao != "ADICIONAR":
        print("Operação cancelada.")
        return

    resultados = []

    for erro in erros_plano:
        resultados.append({
            "email": erro["email"],
            "user_id": erro["user_id"],
            "grupo": erro["grupo"],
            "group_id": erro["group_id"],
            "status": "ERRO_PLANO",
            "detalhe": erro["tipo_erro"],
        })

    for numero, item in enumerate(plano, start=1):
        print("\n" + "-" * 76)
        print(
            f"[{numero}/{len(plano)}] "
            f"{item['email']} -> {item['grupo']}"
        )

        try:
            api.post(
                (
                    f"/api/v2/groups/"
                    f"{item['group_id']}/members"
                ),
                json={
                    "memberIds": [
                        item["user_id"]
                    ]
                },
            )

            if confirmar(
                api,
                item["group_id"],
                item["user_id"],
            ):
                status = "CONFIRMADA"
                detalhe = ""
                print("  OK: associação confirmada.")
            else:
                status = "NAO_CONFIRMADA"
                detalhe = (
                    "Usuário não confirmado no grupo "
                    "após nova consulta."
                )
                print(
                    "  ATENÇÃO: associação não confirmada."
                )

        except Exception as erro:
            status = "ERRO"
            detalhe = str(erro)
            print(f"  ERRO: {erro}")

        resultados.append({
            "email": item["email"],
            "user_id": item["user_id"],
            "grupo": item["grupo"],
            "group_id": item["group_id"],
            "status": status,
            "detalhe": detalhe,
        })

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    arquivo = os.path.join(
        OUTPUT_DIR,
        f"adicao_grupo_{timestamp}.csv",
    )

    campos = [
        "email",
        "user_id",
        "grupo",
        "group_id",
        "status",
        "detalhe",
    ]

    with open(
        arquivo,
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=campos,
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(resultados)

    confirmadas = sum(
        item["status"] == "CONFIRMADA"
        for item in resultados
    )

    nao_confirmadas = sum(
        item["status"] == "NAO_CONFIRMADA"
        for item in resultados
    )

    erros = sum(
        item["status"] in (
            "ERRO",
            "ERRO_PLANO",
        )
        for item in resultados
    )

    print("\n" + "=" * 76)
    print("FINALIZADO")
    print("=" * 76)
    print(f"Alterações confirmadas: {confirmadas}")
    print(f"Não confirmadas:        {nao_confirmadas}")
    print(f"Erros:                  {erros}")
    print(f"Log: {arquivo}")


if __name__ == "__main__":
    main()
