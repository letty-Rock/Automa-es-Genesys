import csv
import glob
import os
import unicodedata
from config import OUTPUT_DIR
try:
    from config import FILAS_PROTEGIDAS, SKILLS_PROTEGIDAS
except ImportError:
    FILAS_PROTEGIDAS = []
    SKILLS_PROTEGIDAS = []
SEPARADOR_LISTA = "|"

def normalizar(texto):
    return (texto or "").strip().casefold()

def esta_protegido(nome, lista):
    return normalizar(nome) in {normalizar(x) for x in (lista or []) if normalizar(x)}

def localizar_backup_mais_recente():
    arquivos = glob.glob(os.path.join(OUTPUT_DIR, "backup_genesys_*.csv"))
    if not arquivos:
        raise FileNotFoundError(f"Nenhum backup_genesys_*.csv encontrado em: {OUTPUT_DIR}")
    return max(arquivos, key=os.path.getmtime)

def separar(valor):
    return [x.strip() for x in (valor or "").split(SEPARADOR_LISTA) if x.strip()]

def main():
    print("=" * 78)
    print("DIAGNÓSTICO DAS PROTEÇÕES DO SCRIPT 02")
    print("SOMENTE LEITURA - NÃO ALTERA NADA NO GENESYS")
    print("=" * 78)
    backup = localizar_backup_mais_recente()
    print(f"\nBackup analisado: {os.path.abspath(backup)}")
    print("\nSKILLS_PROTEGIDAS carregadas do config.py:")
    for x in SKILLS_PROTEGIDAS or []:
        print(f"  {repr(x)} -> {repr(normalizar(x))}")

    resultados = []
    with open(backup, "r", encoding="utf-8-sig", newline="") as arq:
        reader = csv.DictReader(arq, delimiter=";")
        if "skills" not in (reader.fieldnames or []):
            raise ValueError("O backup não possui a coluna 'skills'.")
        for linha_numero, linha in enumerate(reader, 2):
            if (linha.get("status") or "").strip() != "OK":
                continue
            email = (linha.get("email") or "").strip()
            for skill in separar(linha.get("skills")):
                protegida = esta_protegido(skill, SKILLS_PROTEGIDAS)
                resultados.append({
                    "linha_backup": linha_numero,
                    "email": email,
                    "skill_backup": skill,
                    "repr_skill": repr(skill),
                    "skill_normalizada": normalizar(skill),
                    "protegida": "SIM" if protegida else "NAO",
                    "unicode": " ".join(f"U+{ord(c):04X}" for c in skill),
                    "nomes_unicode": " | ".join(unicodedata.name(c, "SEM_NOME") for c in skill),
                })

    print("\nSKILLS ENCONTRADAS NO BACKUP")
    print("-" * 78)
    for item in resultados:
        marca = "PROTEGIDA" if item["protegida"] == "SIM" else "REMOVERIA"
        print(f"[{marca}] {item['email']} -> {item['repr_skill']}")

    alvo = "Atendimento Especializado"
    print("\n" + "=" * 78)
    print(f"TESTE ESPECÍFICO: {alvo}")
    print("=" * 78)
    exatos = [x for x in resultados if x["skill_normalizada"] == normalizar(alvo)]
    if exatos:
        for x in exatos:
            print(f"{x['email']} -> protegida={x['protegida']} | {x['repr_skill']}")
    else:
        print("Nenhuma correspondência exata após strip().casefold().")
        for x in resultados:
            if "atendimento" in x["skill_normalizada"] or "especializado" in x["skill_normalizada"]:
                print(f"PARECIDA: {x['email']} -> {x['repr_skill']} | {repr(x['skill_normalizada'])}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    saida = os.path.abspath(os.path.join(OUTPUT_DIR, "diagnostico_protecao_skills.csv"))
    campos = ["linha_backup", "email", "skill_backup", "repr_skill", "skill_normalizada", "protegida", "unicode", "nomes_unicode"]
    with open(saida, "w", encoding="utf-8-sig", newline="") as arq:
        w = csv.DictWriter(arq, fieldnames=campos, delimiter=";")
        w.writeheader()
        w.writerows(resultados)
    print("\n" + "=" * 78)
    print("RESUMO")
    print("=" * 78)
    print(f"Skills analisadas: {len(resultados)}")
    print(f"Protegidas reconhecidas: {sum(x['protegida'] == 'SIM' for x in resultados)}")
    print(f"CSV: {saida}")
    print("Nenhuma alteração foi feita no Genesys.")

if __name__ == "__main__":
    main()
