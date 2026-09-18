import time
import requests

from config import (
    LOGIN_URL,
    API_URL,
    CLIENT_ID,
    CLIENT_SECRET,
    REQUEST_DELAY,
    MAX_RETRIES,
)


class GenesysAPI:
    """
    Cliente para comunicação com a Genesys Cloud Platform API.

    Responsável por:
    - OAuth Client Credentials
    - GET / POST / PUT / DELETE
    - Tratamento de HTTP 429
    - Retry de erros temporários
    - Paginação
    """

    def __init__(self):
        self.session = requests.Session()
        self.token = None

    # ========================================================
    # AUTENTICAÇÃO
    # ========================================================

    def autenticar(self):

        # As credenciais são carregadas diretamente do config.py
        if not CLIENT_ID or not CLIENT_SECRET:
            raise RuntimeError(
                "\nCredenciais não encontradas no config.py.\n\n"
                "Verifique se CLIENT_ID e CLIENT_SECRET estão "
                "preenchidos corretamente no arquivo config.py.\n"
            )

        print("Autenticando no Genesys Cloud...")

        url = f"{LOGIN_URL.rstrip('/')}/oauth/token"

        try:
            response = requests.post(
                url,
                auth=(CLIENT_ID, CLIENT_SECRET),
                data={
                    "grant_type": "client_credentials"
                },
                timeout=30,
            )

        except requests.RequestException as erro:
            raise RuntimeError(
                "\nErro de conexão durante a autenticação.\n"
                f"URL: {url}\n"
                f"Erro: {erro}\n"
            ) from erro

        if response.status_code != 200:
            raise RuntimeError(
                "\nErro na autenticação Genesys Cloud.\n"
                f"HTTP: {response.status_code}\n"
                f"URL: {url}\n"
                f"Resposta: {response.text}\n"
            )

        dados = response.json()

        self.token = dados.get("access_token")

        if not self.token:
            raise RuntimeError(
                "A Genesys respondeu à autenticação, "
                "mas não retornou access_token."
            )

        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

        print("Autenticação realizada com sucesso.")

    # ========================================================
    # REQUEST GENÉRICO
    # ========================================================

    def request(self, method, endpoint, **kwargs):

        if not self.token:
            raise RuntimeError(
                "Cliente não autenticado. "
                "Execute api.autenticar() primeiro."
            )

        # Evita problemas com barras duplicadas
        url = (
            f"{API_URL.rstrip('/')}/"
            f"{endpoint.lstrip('/')}"
        )

        for tentativa in range(1, MAX_RETRIES + 1):

            try:

                response = self.session.request(
                    method=method,
                    url=url,
                    timeout=60,
                    **kwargs,
                )

            except requests.RequestException as erro:

                if tentativa >= MAX_RETRIES:
                    raise RuntimeError(
                        "\nFalha de conexão com a Genesys Cloud.\n"
                        f"Tentativas: {MAX_RETRIES}\n"
                        f"URL: {url}\n"
                        f"Erro: {erro}\n"
                    ) from erro

                espera = min(2 ** tentativa, 30)

                print(
                    f"Erro de conexão. "
                    f"Nova tentativa em {espera}s..."
                )

                time.sleep(espera)

                continue

            # =================================================
            # TOKEN EXPIRADO / NÃO AUTORIZADO
            # =================================================

            if response.status_code == 401:

                if tentativa < MAX_RETRIES:

                    print(
                        "Token expirado ou não autorizado. "
                        "Autenticando novamente..."
                    )

                    self.autenticar()

                    continue

                raise RuntimeError(
                    "\nErro de autenticação/autorização.\n"
                    f"HTTP: 401\n"
                    f"Endpoint: {endpoint}\n"
                    f"Resposta: {response.text}\n"
                )

            # =================================================
            # RATE LIMIT
            # =================================================

            if response.status_code == 429:

                retry_after = response.headers.get(
                    "Retry-After"
                )

                try:
                    espera = max(
                        float(retry_after),
                        1.0
                    )

                except (TypeError, ValueError):

                    espera = min(
                        2 ** tentativa,
                        30
                    )

                if tentativa >= MAX_RETRIES:
                    raise RuntimeError(
                        "\nRate limit persistente.\n"
                        f"HTTP: 429\n"
                        f"Endpoint: {endpoint}\n"
                        f"Tentativas: {MAX_RETRIES}\n"
                        f"Resposta: {response.text}\n"
                    )

                print(
                    f"Rate limit (HTTP 429). "
                    f"Aguardando {espera:g}s..."
                )

                time.sleep(espera)

                continue

            # =================================================
            # ERROS TEMPORÁRIOS
            # =================================================

            if response.status_code in (
                500,
                502,
                503,
                504,
            ):

                if tentativa >= MAX_RETRIES:

                    raise RuntimeError(
                        "\nErro temporário persistente "
                        "na Genesys Cloud.\n"
                        f"HTTP: {response.status_code}\n"
                        f"Endpoint: {endpoint}\n"
                        f"Tentativas: {MAX_RETRIES}\n"
                        f"Resposta: {response.text}\n"
                    )

                espera = min(
                    2 ** tentativa,
                    30
                )

                print(
                    f"HTTP {response.status_code}. "
                    f"Nova tentativa em {espera}s..."
                )

                time.sleep(espera)

                continue

            # =================================================
            # OUTROS ERROS HTTP
            # =================================================

            if response.status_code >= 400:

                raise RuntimeError(
                    "\nErro na Genesys Cloud API\n"
                    f"HTTP: {response.status_code}\n"
                    f"Método: {method}\n"
                    f"URL: {url}\n"
                    f"Endpoint: {endpoint}\n"
                    f"Resposta: {response.text}\n"
                )

            # Pequeno intervalo entre chamadas
            if REQUEST_DELAY:
                time.sleep(REQUEST_DELAY)

            # DELETE normalmente retorna 204
            if response.status_code == 204:
                return None

            if not response.text:
                return None

            try:
                return response.json()

            except ValueError:
                return response.text

        raise RuntimeError(
            f"Falha após {MAX_RETRIES} tentativas."
        )

    # ========================================================
    # MÉTODOS HTTP
    # ========================================================

    def get(self, endpoint, **kwargs):
        return self.request(
            "GET",
            endpoint,
            **kwargs,
        )

    def post(self, endpoint, **kwargs):
        return self.request(
            "POST",
            endpoint,
            **kwargs,
        )

    def put(self, endpoint, **kwargs):
        return self.request(
            "PUT",
            endpoint,
            **kwargs,
        )

    def delete(self, endpoint, **kwargs):
        return self.request(
            "DELETE",
            endpoint,
            **kwargs,
        )

    # ========================================================
    # PAGINAÇÃO
    # ========================================================

    def get_all_pages(
        self,
        endpoint,
        page_size=100,
        extra_params=None,
    ):

        entidades = []
        pagina = 1

        while True:

            params = {
                "pageSize": page_size,
                "pageNumber": pagina,
            }

            if extra_params:
                params.update(extra_params)

            dados = self.get(
                endpoint,
                params=params,
            )

            if not dados:
                break

            # A maioria dos endpoints paginados da Genesys
            # utiliza "entities".
            itens = dados.get(
                "entities",
                []
            )

            entidades.extend(itens)

            page_count = dados.get(
                "pageCount",
                1
            )

            if pagina >= page_count:
                break

            pagina += 1

        return entidades