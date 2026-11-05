import argparse
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ponte import assinar


def main():
    parser = argparse.ArgumentParser(description="Envia um evento fictício ao receptor local.")
    parser.add_argument("--porta", type=int, default=8765)
    parser.add_argument("--total", type=int, default=18990)
    args = parser.parse_args()
    segredo = os.environ.get("PONTE_SEGREDO", "").encode("utf-8")
    if not segredo:
        parser.error("Defina PONTE_SEGREDO com o mesmo valor usado no receptor.")
    corpo = json.dumps({
        "tipo": "pedido.criado", "evento_id": "evt-001",
        "pedido_id": "pd-101", "total_centavos": args.total,
    }).encode("utf-8")
    requisicao = Request(
        f"http://127.0.0.1:{args.porta}/webhooks/pedidos",
        data=corpo,
        headers={"Content-Type": "application/json", "X-Assinatura": assinar(corpo, segredo)},
    )
    try:
        with urlopen(requisicao, timeout=5) as resposta:
            print(resposta.status, resposta.read().decode("utf-8"))
    except HTTPError as erro:
        with erro:
            print(erro.code, erro.read().decode("utf-8"))
        raise SystemExit(1)
    except URLError as erro:
        parser.exit(1, f"Não foi possível acessar o receptor: {erro.reason}\n")


if __name__ == "__main__":
    main()
