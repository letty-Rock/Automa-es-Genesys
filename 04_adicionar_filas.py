import argparse
import csv
import os
import time
from datetime import datetime

from genesys_api import GenesysAPI
from config import OUTPUT_DIR

QUEUES_FILE = "filas.csv"


def ler_csv(caminho):
    with open(caminho, "r", encoding="utf-8-sig", newline="") as arquivo:
        return list(csv.DictReader(arquivo, delimiter=";"))


def carregar_filas():
    """
    Modelo esperado:

    email;user_id;fila;queue_id

    user_id e queue_id podem ficar vazios em arquivos montados manualmente.
    O vínculo principal é: email -> fila.
    """
    linhas = ler_csv(QUEUES_FILE)
    registros = []

    for numero, linha in enumerate(linhas, start=2):
        email = (linha.get("email") or "").strip()
        user_id = (linha.get("user_id") or "").strip()
        nome = (
            linha.get("fila")
            or linha.get("queue")
            or linha.get("name")
            or ""
        ).strip()
        queue_id = (linha.get("queue_id") or "").strip()

        if not email and not nome and not queue_id:
            continue

        if not email:
            raise ValueError(
                f"Linha {numero}: email não informado."
            )

        if not nome:
            raise ValueError(
                f"Linha {numero}: fila não informada."
            )

        registros.append({
            "email": email,
            "user_id_csv": user_id,
            "name": nome,
            "queue_id_csv": queue_id,
            "linha": numero,
        })

    if not registros:
        raise ValueError(
            "Nenhuma fila encontrada em filas.csv. "
            "Use: email;user_id;fila;queue_id"
        )

    return registros


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

    dados = api.post("/api/v2/users/search", json=payload)

    for usuario in dados.get("results") or dados.get("entities") or []:
        email_api = (usuario.get("email") or "").strip().lower()
        username_api = (usuario.get("username") or "").strip().lower()

        if email.lower() in (email_api, username_api):
            return usuario

    return None


def buscar_fila(api, nome):
    pagina = 1

    while True:
        dados = api.get(
            "/api/v2/routing/queues",
            params={
                "pageSize": 100,
                "pageNumber": pagina,
                "name": nome,
            },
        )

        for fila in dados.get("entities", []):
            if (fila.get("name") or "").strip().lower() == nome.lower():
                return fila

        if pagina >= int(dados.get("pageCount") or 1):
            return None

        pagina += 1


def buscar_fila_por_id(api, queue_id):
    try:
        return api.get(
            f"/api/v2/routing/queues/{queue_id}"
        )
    except Exception:
        return None


def filas_usuario(api, user_id):
    return api.get_all_pages(
        f"/api/v2/users/{user_id}/queues"
    )


def existe(itens, queue_id):
    return any(
        str(item.get("id")) == str(queue_id)
        for item in itens
    )


def confirmar(api, user_id, queue_id):
    for tentativa in range(4):
        if existe(filas_usuario(api, user_id), queue_id):
            return True

        if tentativa < 3:
            time.sleep(2)

    return False


def main():
    parser = argparse.ArgumentParser(
        description="04 - Adiciona filas aos usuários conforme filas.csv."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Executa as alterações. Sem isso, apenas DRY RUN.",
    )
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    registros = carregar_filas()

    api = GenesysAPI()
    api.autenticar()

    print("=" * 76)
    print("04 - ADICIONAR FILAS")
    print("=" * 76)
    print(f"Arquivo: {QUEUES_FILE}")
    print(f"Registros no CSV: {len(registros)}")
    print("Modo:", "EXECUÇÃO" if args.execute else "DRY RUN")
    print()

    usuarios_cache = {}
    filas_nome_cache = {}
    filas_usuario_cache = {}

    plano = []
    erros_plano = []
    associacoes_planejadas = set()

    for numero, item in enumerate(registros, start=1):
        email = item["email"]
        nome_csv = item["name"]

        print(
            f"[{numero}/{len(registros)}] "
            f"{email} -> {nome_csv}"
        )

        # ------------------------------------------------------------
        # USUÁRIO
        # ------------------------------------------------------------
        chave_email = email.lower()

        if chave_email not in usuarios_cache:
            usuarios_cache[chave_email] = buscar_usuario(api, email)

        usuario = usuarios_cache[chave_email]

        if not usuario:
            detalhe = "USUÁRIO NÃO ENCONTRADO"
            print(f"  {detalhe}")
            erros_plano.append({
                **item,
                "tipo_erro": detalhe,
            })
            continue

        user_id = usuario["id"]

        if item["user_id_csv"] and item["user_id_csv"] != user_id:
            print(
                "  ATENÇÃO: user_id do CSV é diferente do "
                "user_id encontrado pelo email."
            )
            print(f"  CSV:     {item['user_id_csv']}")
            print(f"  Genesys: {user_id}")
            print("  Será usado o usuário encontrado pelo email.")

        # ------------------------------------------------------------
        # FILA
        # Primeiro tenta o queue_id do CSV.
        # Se o ID não existir no ambiente atual, tenta pelo nome.
        # ------------------------------------------------------------
        fila = None

        if item["queue_id_csv"]:
            fila = buscar_fila_por_id(
                api,
                item["queue_id_csv"],
            )

            if fila:
                print("  FILA LOCALIZADA PELO queue_id DO CSV.")

        if fila is None and nome_csv:
            chave_nome = nome_csv.strip().lower()

            if chave_nome not in filas_nome_cache:
                filas_nome_cache[chave_nome] = buscar_fila(
                    api,
                    nome_csv,
                )

            fila = filas_nome_cache[chave_nome]

            if fila:
                print("  FILA LOCALIZADA PELO NOME.")

        if not fila:
            detalhe = "FILA NÃO ENCONTRADA"
            print(f"  {detalhe}")
            erros_plano.append({
                **item,
                "tipo_erro": detalhe,
            })
            continue

        queue_id = fila["id"]
        queue_name = fila.get("name") or nome_csv

        if (
            item["queue_id_csv"]
            and item["queue_id_csv"] != queue_id
        ):
            print("  INFO: queue_id atual é diferente do CSV.")
            print(f"  CSV:     {item['queue_id_csv']}")
            print(f"  Genesys: {queue_id}")
            print("  Será usado o ID encontrado na Genesys.")

        # ------------------------------------------------------------
        # ESTADO ATUAL DO USUÁRIO
        # ------------------------------------------------------------
        if user_id not in filas_usuario_cache:
            filas_usuario_cache[user_id] = filas_usuario(
                api,
                user_id,
            )

        atuais = filas_usuario_cache[user_id]

        if existe(atuais, queue_id):
            print("  JÁ ESTÁ NA FILA.")
            continue

        chave_associacao = (str(user_id), str(queue_id))

        if chave_associacao in associacoes_planejadas:
            print("  DUPLICADA NO CSV: associação já planejada.")
            continue

        associacoes_planejadas.add(chave_associacao)

        print(f"  AÇÃO: ADICIONAR {queue_name}")

        plano.append({
            "email": email,
            "user_id": user_id,
            "fila": queue_name,
            "queue_id": queue_id,
        })

    print("\n" + "=" * 76)
    print("RESUMO")
    print("=" * 76)
    print(f"Filas a adicionar:               {len(plano)}")
    print(f"Registros com erro no plano:     {len(erros_plano)}")
    print(f"Total de alterações planejadas:  {len(plano)}")

    if not args.execute:
        print("\nDRY RUN: nenhuma alteração foi realizada.")
        print(
            r"Para executar: "
            r"py .\04_adicionar_filas.py --execute"
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

    log = []

    # Inclui erros encontrados durante o planejamento.
    for erro in erros_plano:
        log.append({
            "email": erro["email"],
            "user_id": erro["user_id_csv"],
            "fila": erro["name"],
            "queue_id": erro["queue_id_csv"],
            "status": "ERRO_PLANO",
            "detalhe": erro["tipo_erro"],
        })

    for numero, item in enumerate(plano, start=1):
        print("\n" + "-" * 76)
        print(
            f"[{numero}/{len(plano)}] "
            f"{item['email']} -> {item['fila']}"
        )

        try:
            api.post(
                f"/api/v2/routing/queues/{item['queue_id']}/members",
                json=[{"id": item["user_id"]}],
            )

            if confirmar(
                api,
                item["user_id"],
                item["queue_id"],
            ):
                status = "CONFIRMADA"
                detalhe = ""
                print("  OK: associação confirmada.")
            else:
                status = "NAO_CONFIRMADA"
                detalhe = (
                    "Associação com a fila não confirmada "
                    "após nova consulta."
                )
                print("  ATENÇÃO: associação não confirmada.")

        except Exception as erro:
            status = "ERRO"
            detalhe = str(erro)
            print(f"  ERRO: {erro}")

        log.append({
            "email": item["email"],
            "user_id": item["user_id"],
            "fila": item["fila"],
            "queue_id": item["queue_id"],
            "status": status,
            "detalhe": detalhe,
        })

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(
        OUTPUT_DIR,
        f"adicao_filas_{timestamp}.csv",
    )

    campos = [
        "email",
        "user_id",
        "fila",
        "queue_id",
        "status",
        "detalhe",
    ]

    with open(
        path,
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as arquivo:
        writer = csv.DictWriter(
            arquivo,
            fieldnames=campos,
            delimiter=";",
        )
        writer.writeheader()
        writer.writerows(log)

    confirmadas = sum(
        item["status"] == "CONFIRMADA"
        for item in log
    )
    nao_confirmadas = sum(
        item["status"] == "NAO_CONFIRMADA"
        for item in log
    )
    erros = sum(
        item["status"] in ("ERRO", "ERRO_PLANO")
        for item in log
    )

    print("\n" + "=" * 76)
    print("FINALIZADO")
    print("=" * 76)
    print(f"Alterações confirmadas: {confirmadas}")
    print(f"Não confirmadas:        {nao_confirmadas}")
    print(f"Erros:                  {erros}")
    print(f"Log: {path}")


if __name__ == "__main__":
    main()
