import argparse
import csv
import os
import time
from datetime import datetime

from genesys_api import GenesysAPI
from config import OUTPUT_DIR

SKILLS_FILE = "skills.csv"


def ler_csv(caminho):
    with open(caminho, "r", encoding="utf-8-sig", newline="") as arquivo:
        return list(csv.DictReader(arquivo, delimiter=";"))


def carregar_skills():
    """
    Modelo esperado:

    email;user_id;skill;skill_id;proficiency

    user_id e skill_id podem ficar vazios em arquivos montados manualmente.
    O vínculo principal é: email -> skill -> proficiency.
    """
    linhas = ler_csv(SKILLS_FILE)
    skills = []

    for numero, linha in enumerate(linhas, start=2):
        email = (linha.get("email") or "").strip()
        user_id = (linha.get("user_id") or "").strip()
        nome = (linha.get("skill") or linha.get("name") or "").strip()
        skill_id = (linha.get("skill_id") or "").strip()
        valor = (
            linha.get("proficiency")
            or linha.get("proficiencia")
            or ""
        ).strip()

        # Ignora linha totalmente vazia
        if not email and not nome and not valor:
            continue

        if not email:
            raise ValueError(
                f"Linha {numero}: email não informado."
            )

        if not nome and not skill_id:
            raise ValueError(
                f"Linha {numero}: informe skill ou skill_id."
            )

        if valor == "":
            raise ValueError(
                f"Linha {numero}: proficiency não informada para "
                f"'{nome or skill_id}'."
            )

        try:
            proficiency = float(valor.replace(",", "."))
        except ValueError:
            raise ValueError(
                f"Linha {numero}: proficiency inválida "
                f"para '{nome or skill_id}': {valor}"
            )

        if not 0 <= proficiency <= 5:
            raise ValueError(
                f"Linha {numero}: proficiency de "
                f"'{nome or skill_id}' deve estar entre 0 e 5."
            )

        skills.append({
            "email": email,
            "user_id_csv": user_id,
            "name": nome,
            "skill_id_csv": skill_id,
            "proficiency": proficiency,
            "linha": numero,
        })

    if not skills:
        raise ValueError(
            "Nenhuma skill encontrada em skills.csv. "
            "Use: email;user_id;skill;skill_id;proficiency"
        )

    return skills


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


def buscar_skill_por_nome(api, nome):
    pagina = 1

    while True:
        dados = api.get(
            "/api/v2/routing/skills",
            params={
                "pageSize": 100,
                "pageNumber": pagina,
            },
        )

        for skill in dados.get("entities", []):
            if (skill.get("name") or "").strip().lower() == nome.lower():
                return skill

        if pagina >= int(dados.get("pageCount") or 1):
            return None

        pagina += 1


def buscar_skill_por_id(api, skill_id):
    try:
        return api.get(f"/api/v2/routing/skills/{skill_id}")
    except Exception:
        return None


def resolver_skill(api, item):
    """
    Se skill_id existir no CSV, tenta primeiro pelo ID.
    Se não existir ou não for encontrado, tenta pelo nome.
    """
    skill_id = item["skill_id_csv"]
    nome = item["name"]

    if skill_id:
        skill = buscar_skill_por_id(api, skill_id)
        if skill:
            return skill

    if nome:
        return buscar_skill_por_nome(api, nome)

    return None


def skills_usuario(api, user_id):
    return api.get_all_pages(
        f"/api/v2/users/{user_id}/routingskills"
    )


def achar_skill(itens, skill_id):
    return next(
        (
            item
            for item in itens
            if str(item.get("id")) == str(skill_id)
        ),
        None,
    )


def confirmar(api, user_id, skill_id, proficiency):
    for tentativa in range(4):
        atual = achar_skill(
            skills_usuario(api, user_id),
            skill_id,
        )

        if atual is not None:
            prof_atual = float(atual.get("proficiency") or 0)

            if abs(prof_atual - proficiency) < 0.0001:
                return True

        if tentativa < 3:
            time.sleep(2)

    return False


def main():
    parser = argparse.ArgumentParser(
        description=(
            "03 - Adiciona skills aos usuários conforme skills.csv."
        )
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Executa as alterações. Sem isso, apenas DRY RUN.",
    )
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    registros = carregar_skills()

    api = GenesysAPI()
    api.autenticar()

    print("=" * 76)
    print("03 - ADICIONAR SKILLS")
    print("=" * 76)
    print(f"Arquivo: {SKILLS_FILE}")
    print(f"Registros no CSV: {len(registros)}")
    print("Modo:", "EXECUÇÃO" if args.execute else "DRY RUN")
    print()

    # Cache para não consultar o mesmo usuário/skill várias vezes.
    usuarios_cache = {}
    skills_nome_cache = {}
    skills_usuario_cache = {}

    plano = []
    erros_plano = []

    for numero, item in enumerate(registros, start=1):
        email = item["email"]
        nome_csv = item["name"]
        proficiency = item["proficiency"]

        print(
            f"[{numero}/{len(registros)}] "
            f"{email} -> {nome_csv or item['skill_id_csv']} "
            f"({proficiency})"
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

        # Se o CSV tiver user_id, apenas avisamos se estiver diferente.
        if item["user_id_csv"] and item["user_id_csv"] != user_id:
            print(
                "  ATENÇÃO: user_id do CSV é diferente do "
                "user_id encontrado pelo email."
            )
            print(f"  CSV:     {item['user_id_csv']}")
            print(f"  Genesys: {user_id}")
            print("  Será usado o usuário encontrado pelo email.")

        # ------------------------------------------------------------
        # SKILL
        # ------------------------------------------------------------
        # Sempre localiza a skill pelo NOME no ambiente atual.
        # skill_id do CSV fica apenas como referência/backup.
        skill = None

        if nome_csv:
            chave_nome = nome_csv.strip().lower()

            if chave_nome not in skills_nome_cache:
                skills_nome_cache[chave_nome] = buscar_skill_por_nome(
                    api,
                    nome_csv,
                )

            skill = skills_nome_cache[chave_nome]

        if not skill:
            detalhe = "SKILL NÃO ENCONTRADA"
            print(f"  {detalhe}")
            erros_plano.append({
                **item,
                "tipo_erro": detalhe,
            })
            continue

        skill_id = skill["id"]
        skill_name = skill.get("name") or nome_csv

        if (
            item["skill_id_csv"]
            and item["skill_id_csv"] != skill_id
        ):
            print("  INFO: skill_id atual é diferente do CSV.")
            print(f"  CSV:     {item['skill_id_csv']}")
            print(f"  Genesys: {skill_id}")
            print("  Será usado o ID localizado pelo nome da skill.")

        # ------------------------------------------------------------
        # ESTADO ATUAL DO USUÁRIO
        # ------------------------------------------------------------
        if user_id not in skills_usuario_cache:
            skills_usuario_cache[user_id] = skills_usuario(
                api,
                user_id,
            )

        atuais = skills_usuario_cache[user_id]
        atual = achar_skill(atuais, skill_id)

        if atual is None:
            acao = "ADICIONAR"
            print(f"  AÇÃO: ADICIONAR {skill_name}")
        else:
            prof_atual = float(atual.get("proficiency") or 0)

            if abs(prof_atual - proficiency) < 0.0001:
                print(
                    f"  JÁ ESTÁ CORRETO: proficiency {prof_atual}"
                )
                continue

            acao = "ATUALIZAR_PROFICIENCY"
            print(
                f"  AÇÃO: ATUALIZAR proficiency "
                f"{prof_atual} -> {proficiency}"
            )

        plano.append({
            "email": email,
            "user_id": user_id,
            "skill": skill_name,
            "skill_id": skill_id,
            "proficiency": proficiency,
            "acao": acao,
        })

    print("\n" + "=" * 76)
    print("RESUMO")
    print("=" * 76)

    adicionar = sum(
        item["acao"] == "ADICIONAR"
        for item in plano
    )
    atualizar = sum(
        item["acao"] == "ATUALIZAR_PROFICIENCY"
        for item in plano
    )

    print(f"Skills a adicionar:              {adicionar}")
    print(f"Proficiencies a atualizar:       {atualizar}")
    print(f"Registros com erro no plano:     {len(erros_plano)}")
    print(f"Total de alterações planejadas:  {len(plano)}")

    if not args.execute:
        print("\nDRY RUN: nenhuma alteração foi realizada.")
        print(
            r"Para executar: "
            r"py .\03_adicionar_skills.py --execute"
        )
        return

    if not plano:
        print("\nNada para adicionar ou atualizar.")
        return

    confirmacao = input(
        "\nDigite ADICIONAR para continuar: "
    ).strip()

    if confirmacao != "ADICIONAR":
        print("Operação cancelada.")
        return

    log = []

    # Inclui erros encontrados durante o planejamento no log.
    for erro in erros_plano:
        log.append({
            "email": erro["email"],
            "user_id": erro["user_id_csv"],
            "skill": erro["name"],
            "skill_id": erro["skill_id_csv"],
            "proficiency": erro["proficiency"],
            "acao": "",
            "status": "ERRO_PLANO",
            "detalhe": erro["tipo_erro"],
        })

    for numero, item in enumerate(plano, start=1):
        print("\n" + "-" * 76)
        print(
            f"[{numero}/{len(plano)}] "
            f"{item['email']} -> {item['skill']}"
        )
        print(
            f"Proficiency: {item['proficiency']} | "
            f"Ação: {item['acao']}"
        )

        try:
            if item["acao"] == "ADICIONAR":
                # Skill ainda não está associada ao usuário:
                # cria a associação.
                api.post(
                    f"/api/v2/users/{item['user_id']}/routingskills",
                    json={
                        "id": item["skill_id"],
                        "name": item["skill"],
                        "proficiency": item["proficiency"],
                    },
                )
            else:
                # Skill já existe no usuário:
                # atualiza somente a associação/proficiency.
                api.put(
                    (
                        f"/api/v2/users/{item['user_id']}"
                        f"/routingskills/{item['skill_id']}"
                    ),
                    json={
                        "id": item["skill_id"],
                        "name": item["skill"],
                        "proficiency": item["proficiency"],
                    },
                )

            if confirmar(
                api,
                item["user_id"],
                item["skill_id"],
                item["proficiency"],
            ):
                status = "CONFIRMADA"
                detalhe = ""
                print("  OK: alteração confirmada.")
            else:
                status = "NAO_CONFIRMADA"
                detalhe = (
                    "Skill/proficiency não confirmada "
                    "após nova consulta."
                )
                print("  ATENÇÃO: alteração não confirmada.")

        except Exception as erro:
            status = "ERRO"
            detalhe = str(erro)
            print(f"  ERRO: {erro}")

        log.append({
            "email": item["email"],
            "user_id": item["user_id"],
            "skill": item["skill"],
            "skill_id": item["skill_id"],
            "proficiency": item["proficiency"],
            "acao": item["acao"],
            "status": status,
            "detalhe": detalhe,
        })

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = os.path.join(
        OUTPUT_DIR,
        f"adicao_skills_{timestamp}.csv",
    )

    campos = [
        "email",
        "user_id",
        "skill",
        "skill_id",
        "proficiency",
        "acao",
        "status",
        "detalhe",
    ]

    with open(
        log_path,
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
    print(f"Log: {log_path}")


if __name__ == "__main__":
    main()
