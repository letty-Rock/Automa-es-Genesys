import argparse
import csv
import glob
import os
import time
from datetime import datetime

from genesys_api import GenesysAPI
from config import OUTPUT_DIR

try:
    from config import FILAS_PROTEGIDAS, SKILLS_PROTEGIDAS
except ImportError:
    FILAS_PROTEGIDAS = []
    SKILLS_PROTEGIDAS = []


SEPARADOR_LISTA = "|"
TENTATIVAS_CONFIRMACAO = 4
ESPERA_CONFIRMACAO = 2


def normalizar(texto):
    return (texto or "").strip().casefold()


def esta_protegido(nome, lista_protegida):
    return normalizar(nome) in {
        normalizar(item)
        for item in (lista_protegida or [])
        if normalizar(item)
    }


def separar_nome_proficiency_skill(valor):
    """
    O backup pode armazenar a skill como:
        Atendimento Especializado:5.0

    Retorna:
        ("Atendimento Especializado", "5.0")

    Só considera o trecho final como proficiency quando ele é numérico.
    Assim, um ':' legítimo dentro do nome da skill não é removido por engano.
    """
    valor = (valor or "").strip()

    if ":" not in valor:
        return valor, ""

    nome, possivel_proficiency = valor.rsplit(":", 1)
    possivel_proficiency = possivel_proficiency.strip()

    try:
        float(possivel_proficiency)
    except ValueError:
        return valor, ""

    return nome.strip(), possivel_proficiency


def skill_esta_protegida(valor_skill):
    nome_skill, _ = separar_nome_proficiency_skill(valor_skill)
    return esta_protegido(
        nome_skill,
        SKILLS_PROTEGIDAS,
    )


def localizar_backup_mais_recente():
    padrao = os.path.join(
        OUTPUT_DIR,
        "backup_genesys_*.csv",
    )
    arquivos = glob.glob(padrao)

    if not arquivos:
        raise FileNotFoundError(
            f"Nenhum backup encontrado em '{OUTPUT_DIR}'.\n"
            "Execute primeiro: "
            r"py .\01_exportar_filas_skills.py"
        )

    return max(
        arquivos,
        key=os.path.getmtime,
    )


def separar(valor):
    if not valor:
        return []

    return [
        item.strip()
        for item in valor.split(SEPARADOR_LISTA)
        if item.strip()
    ]


def carregar_backup(caminho):
    usuarios = []

    with open(
        caminho,
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as arquivo:
        reader = csv.DictReader(
            arquivo,
            delimiter=";",
        )

        obrigatorias = {
            "email",
            "user_id",
            "status",
            "filas",
            "filas_ids",
            "skills",
            "skills_ids",
        }

        encontradas = set(reader.fieldnames or [])
        faltando = obrigatorias - encontradas

        if faltando:
            raise ValueError(
                "Backup incompatível. Colunas ausentes: "
                + ", ".join(sorted(faltando))
            )

        for linha in reader:
            if (
                (linha.get("status") or "").strip()
                != "OK"
            ):
                continue

            user_id = (
                linha.get("user_id") or ""
            ).strip()

            if not user_id:
                continue

            filas = separar(
                linha.get("filas")
            )
            filas_ids = separar(
                linha.get("filas_ids")
            )
            skills = separar(
                linha.get("skills")
            )
            skills_ids = separar(
                linha.get("skills_ids")
            )

            if len(filas) != len(filas_ids):
                raise ValueError(
                    f"Backup inconsistente para "
                    f"{linha.get('email', '')}: "
                    f"{len(filas)} filas e "
                    f"{len(filas_ids)} IDs de filas."
                )

            if len(skills) != len(skills_ids):
                raise ValueError(
                    f"Backup inconsistente para "
                    f"{linha.get('email', '')}: "
                    f"{len(skills)} skills e "
                    f"{len(skills_ids)} IDs de skills."
                )

            filas_com_ids = list(
                zip(filas, filas_ids)
            )
            skills_com_ids = list(
                zip(skills, skills_ids)
            )

            # Segurança adicional:
            # skills protegidas ficam em uma coleção separada e
            # NUNCA entram na coleção de skills removíveis.
            skills_protegidas_usuario = []
            skills_removiveis_usuario = []

            for valor_skill, skill_id in skills_com_ids:
                if skill_esta_protegida(valor_skill):
                    skills_protegidas_usuario.append(
                        (valor_skill, skill_id)
                    )
                else:
                    skills_removiveis_usuario.append(
                        (valor_skill, skill_id)
                    )

            usuarios.append({
                "email": (
                    linha.get("email") or ""
                ).strip(),
                "user_id": user_id,
                "filas": filas_com_ids,
                "skills": skills_removiveis_usuario,
                "skills_protegidas": skills_protegidas_usuario,
            })

    return usuarios


def filas_atuais(api, user_id):
    return api.get_all_pages(
        f"/api/v2/users/{user_id}/queues"
    )


def skills_atuais(api, user_id):
    return api.get_all_pages(
        f"/api/v2/users/{user_id}/routingskills"
    )


def contem_id(entidades, item_id):
    return any(
        str(item.get("id")) == str(item_id)
        for item in entidades
    )


def confirmar_remocao_fila(
    api,
    user_id,
    queue_id,
):
    for tentativa in range(
        TENTATIVAS_CONFIRMACAO
    ):
        atuais = filas_atuais(
            api,
            user_id,
        )

        if not contem_id(
            atuais,
            queue_id,
        ):
            return True

        if (
            tentativa
            < TENTATIVAS_CONFIRMACAO - 1
        ):
            time.sleep(
                ESPERA_CONFIRMACAO
            )

    return False


def confirmar_remocao_skill(
    api,
    user_id,
    skill_id,
):
    for tentativa in range(
        TENTATIVAS_CONFIRMACAO
    ):
        atuais = skills_atuais(
            api,
            user_id,
        )

        if not contem_id(
            atuais,
            skill_id,
        ):
            return True

        if (
            tentativa
            < TENTATIVAS_CONFIRMACAO - 1
        ):
            time.sleep(
                ESPERA_CONFIRMACAO
            )

    return False


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Remove filas e skills usando o backup "
            "mais recente, preservando itens "
            "protegidos no config.py."
        )
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Executa as remoções. "
            "Sem esta opção, faz apenas DRY RUN."
        ),
    )

    args = parser.parse_args()

    os.makedirs(
        OUTPUT_DIR,
        exist_ok=True,
    )

    backup_path = (
        localizar_backup_mais_recente()
    )

    usuarios = carregar_backup(
        backup_path
    )

    total_filas_remover = 0
    total_skills_remover = 0
    total_filas_protegidas = 0
    total_skills_protegidas = 0

    for usuario in usuarios:
        for nome_fila, _ in usuario["filas"]:
            if esta_protegido(
                nome_fila,
                FILAS_PROTEGIDAS,
            ):
                total_filas_protegidas += 1
            else:
                total_filas_remover += 1

        total_skills_remover += len(
            usuario["skills"]
        )
        total_skills_protegidas += len(
            usuario["skills_protegidas"]
        )

    print("=" * 76)
    print(
        "GENESYS CLOUD - REMOÇÃO DE FILAS E SKILLS"
    )
    print("=" * 76)
    print()
    print(
        f"Backup utilizado:       {backup_path}"
    )
    print(
        f"Usuários:                {len(usuarios)}"
    )
    print(
        f"Filas a remover:         "
        f"{total_filas_remover}"
    )
    print(
        f"Skills a remover:        "
        f"{total_skills_remover}"
    )
    print(
        f"Filas protegidas:        "
        f"{total_filas_protegidas}"
    )
    print(
        f"Skills protegidas:       "
        f"{total_skills_protegidas}"
    )
    print()
    print(
        "Modo:",
        "EXECUÇÃO"
        if args.execute
        else "DRY RUN",
    )

    print()
    print("PROTEÇÕES CONFIGURADAS")
    print("-" * 76)

    if FILAS_PROTEGIDAS:
        print("Filas protegidas:")
        for nome in FILAS_PROTEGIDAS:
            print(f"  - {nome}")
    else:
        print("Filas protegidas: nenhuma")

    if SKILLS_PROTEGIDAS:
        print("Skills protegidas:")
        for nome in SKILLS_PROTEGIDAS:
            print(f"  - {nome}")
    else:
        print("Skills protegidas: nenhuma")

    if not usuarios:
        print(
            "\nNenhum usuário com status OK "
            "encontrado no backup."
        )
        return

    if not args.execute:
        print(
            "\nDRY RUN: nenhuma alteração "
            "será realizada."
        )
    else:
        print()
        print(
            "ATENÇÃO: esta operação modificará "
            "o Genesys Cloud."
        )
        print(
            "Itens PROTEGIDOS não serão removidos."
        )

        confirmacao = input(
            "Digite REMOVER para continuar: "
        ).strip()

        if confirmacao != "REMOVER":
            print("Operação cancelada.")
            return

    api = GenesysAPI()
    api.autenticar()

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    arquivo_log = os.path.join(
        OUTPUT_DIR,
        f"remocao_{timestamp}.csv",
    )

    log = []

    for numero, usuario in enumerate(
        usuarios,
        1,
    ):
        email = usuario["email"]
        user_id = usuario["user_id"]

        print()
        print("-" * 76)
        print(
            f"[{numero}/{len(usuarios)}] "
            f"{email}"
        )
        print(f"User ID: {user_id}")
        print("-" * 76)

        # ====================================================
        # SKILLS PROTEGIDAS
        # ====================================================

        for (
            nome_skill,
            skill_id,
        ) in usuario["skills_protegidas"]:

            nome_skill_limpo, proficiency = (
                separar_nome_proficiency_skill(
                    nome_skill
                )
            )

            detalhe_proficiency = (
                f" (proficiency {proficiency})"
                if proficiency
                else ""
            )

            print(
                f"  SKILL -> PROTEGIDA: "
                f"{nome_skill_limpo}"
                f"{detalhe_proficiency}"
            )

            log.append({
                "email": email,
                "user_id": user_id,
                "tipo": "SKILL",
                "nome": nome_skill_limpo,
                "id": skill_id,
                "status": "PROTEGIDA",
                "detalhe": (
                    "Preservada por SKILLS_PROTEGIDAS "
                    "no config.py. Não entrou na lista "
                    "de remoção."
                ),
            })

        # ====================================================
        # SKILLS REMOVÍVEIS
        # ====================================================

        for (
            nome_skill,
            skill_id,
        ) in usuario["skills"]:

            nome_skill_limpo, proficiency = (
                separar_nome_proficiency_skill(
                    nome_skill
                )
            )

            detalhe_proficiency = (
                f" (proficiency {proficiency})"
                if proficiency
                else ""
            )

            print(
                f"  SKILL -> REMOVER: "
                f"{nome_skill_limpo}"
                f"{detalhe_proficiency}"
            )

            status = "DRY_RUN"
            detalhe = ""

            if args.execute:
                try:
                    atuais = skills_atuais(
                        api,
                        user_id,
                    )

                    if not contem_id(
                        atuais,
                        skill_id,
                    ):
                        status = "JA_AUSENTE"
                        detalhe = (
                            "Skill já não estava "
                            "associada ao usuário."
                        )
                        print(
                            "    JÁ ESTAVA AUSENTE."
                        )

                    else:
                        api.delete(
                            (
                                f"/api/v2/users/"
                                f"{user_id}/"
                                f"routingskills/"
                                f"{skill_id}"
                            )
                        )

                        confirmado = (
                            confirmar_remocao_skill(
                                api,
                                user_id,
                                skill_id,
                            )
                        )

                        if confirmado:
                            status = (
                                "REMOVIDA_CONFIRMADA"
                            )
                            print(
                                "    OK: remoção "
                                "confirmada."
                            )
                        else:
                            status = (
                                "NAO_CONFIRMADA"
                            )
                            detalhe = (
                                "Skill ainda encontrada "
                                "após nova consulta."
                            )
                            print(
                                "    ATENÇÃO: remoção "
                                "não confirmada."
                            )

                except Exception as erro:
                    status = "ERRO"
                    detalhe = str(erro)
                    print(
                        f"    ERRO: {erro}"
                    )

            log.append({
                "email": email,
                "user_id": user_id,
                "tipo": "SKILL",
                "nome": nome_skill_limpo,
                "id": skill_id,
                "status": status,
                "detalhe": detalhe,
            })

        # ====================================================
        # FILAS
        # ====================================================

        for (
            nome_fila,
            queue_id,
        ) in usuario["filas"]:

            if esta_protegido(
                nome_fila,
                FILAS_PROTEGIDAS,
            ):
                print(
                    f"  FILA  -> PROTEGIDA: "
                    f"{nome_fila}"
                )

                log.append({
                    "email": email,
                    "user_id": user_id,
                    "tipo": "QUEUE",
                    "nome": nome_fila,
                    "id": queue_id,
                    "status": "PROTEGIDA",
                    "detalhe": (
                        "Preservada por "
                        "FILAS_PROTEGIDAS "
                        "no config.py."
                    ),
                })

                continue

            print(
                f"  FILA  -> REMOVER: "
                f"{nome_fila}"
            )

            status = "DRY_RUN"
            detalhe = ""

            if args.execute:
                try:
                    atuais = filas_atuais(
                        api,
                        user_id,
                    )

                    if not contem_id(
                        atuais,
                        queue_id,
                    ):
                        status = "JA_AUSENTE"
                        detalhe = (
                            "Fila já não estava "
                            "associada ao usuário."
                        )
                        print(
                            "    JÁ ESTAVA AUSENTE."
                        )

                    else:
                        # Remoção correta de membro
                        # da fila.
                        api.post(
                            (
                                f"/api/v2/routing/"
                                f"queues/{queue_id}/"
                                f"members"
                            ),
                            params={
                                "delete": "true"
                            },
                            json=[
                                {
                                    "id": user_id
                                }
                            ],
                        )

                        confirmado = (
                            confirmar_remocao_fila(
                                api,
                                user_id,
                                queue_id,
                            )
                        )

                        if confirmado:
                            status = (
                                "REMOVIDA_CONFIRMADA"
                            )
                            print(
                                "    OK: remoção "
                                "confirmada."
                            )
                        else:
                            status = (
                                "NAO_CONFIRMADA"
                            )
                            detalhe = (
                                "Fila ainda encontrada "
                                "após nova consulta."
                            )
                            print(
                                "    ATENÇÃO: remoção "
                                "não confirmada."
                            )

                except Exception as erro:
                    status = "ERRO"
                    detalhe = str(erro)
                    print(
                        f"    ERRO: {erro}"
                    )

            log.append({
                "email": email,
                "user_id": user_id,
                "tipo": "QUEUE",
                "nome": nome_fila,
                "id": queue_id,
                "status": status,
                "detalhe": detalhe,
            })

    with open(
        arquivo_log,
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as arquivo:
        writer = csv.DictWriter(
            arquivo,
            fieldnames=[
                "email",
                "user_id",
                "tipo",
                "nome",
                "id",
                "status",
                "detalhe",
            ],
            delimiter=";",
        )

        writer.writeheader()
        writer.writerows(log)

    protegidas = sum(
        item["status"] == "PROTEGIDA"
        for item in log
    )

    print()
    print("=" * 76)
    print("FINALIZADO")
    print("=" * 76)
    print(f"Log: {arquivo_log}")

    if not args.execute:
        planejadas = sum(
            item["status"] == "DRY_RUN"
            for item in log
        )

        print(
            f"Remoções planejadas:     "
            f"{planejadas}"
        )
        print(
            f"Associações protegidas:  "
            f"{protegidas}"
        )
        print(
            "Modo DRY RUN: nenhuma alteração "
            "foi realizada."
        )
        print()
        print("Para executar de verdade:")
        print(
            r"py .\02_remover_filas_skills.py "
            r"--execute"
        )

    else:
        removidas = sum(
            item["status"]
            == "REMOVIDA_CONFIRMADA"
            for item in log
        )

        ja_ausentes = sum(
            item["status"] == "JA_AUSENTE"
            for item in log
        )

        nao_confirmadas = sum(
            item["status"] == "NAO_CONFIRMADA"
            for item in log
        )

        erros = sum(
            item["status"] == "ERRO"
            for item in log
        )

        print(
            f"Remoções confirmadas:    "
            f"{removidas}"
        )
        print(
            f"Associações protegidas:  "
            f"{protegidas}"
        )
        print(
            f"Já ausentes:              "
            f"{ja_ausentes}"
        )
        print(
            f"Não confirmadas:          "
            f"{nao_confirmadas}"
        )
        print(
            f"Erros:                    "
            f"{erros}"
        )


if __name__ == "__main__":
    main()
