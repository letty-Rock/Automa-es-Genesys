from genesys_api import GenesysAPI

EMAIL = "testeleticia3@teste.com.br"

api = GenesysAPI()
api.autenticar()

print(f"\nProcurando: {EMAIL}")
print("=" * 70)

for estado in ["active", "inactive"]:

    print(f"\nTestando state={estado}...")

    resultado = api.get(
        "/api/v2/users",
        params={
            "username": EMAIL,
            "state": estado,
            "pageSize": 100
        }
    )

    usuarios = resultado.get("entities", [])

    print(f"Retornados pela API: {len(usuarios)}")

    for usuario in usuarios:

        print("-" * 70)
        print("Nome:    ", usuario.get("name"))
        print("Email:   ", usuario.get("email"))
        print("Username:", usuario.get("username"))
        print("ID:      ", usuario.get("id"))
        print("State:   ", usuario.get("state"))

print("\nTeste finalizado.")