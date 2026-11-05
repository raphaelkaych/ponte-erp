import argparse
import hashlib
import hmac
import json
import os
import re
import sqlite3
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


LIMITE = 8192
IDENTIFICADOR = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


def assinar(corpo, segredo):
    return "sha256=" + hmac.new(segredo, corpo, hashlib.sha256).hexdigest()


def criar_banco(caminho):
    with closing(sqlite3.connect(caminho)) as banco:
        banco.execute("""
            CREATE TABLE IF NOT EXISTS pedido (
                pedido_id TEXT PRIMARY KEY,
                evento_id TEXT NOT NULL UNIQUE,
                total_centavos INTEGER NOT NULL CHECK (total_centavos > 0)
            )
        """)


def receber(caminho, corpo, assinatura, segredo):
    esperada = assinar(corpo, segredo).encode("ascii")
    if not hmac.compare_digest(esperada, assinatura.encode("utf-8")):
        return 401, {"erro": "assinatura inválida"}
    try:
        evento = json.loads(corpo.decode("utf-8"))
    except (ValueError, RecursionError):
        return 400, {"erro": "JSON inválido"}
    if not isinstance(evento, dict) or evento.get("tipo") != "pedido.criado":
        return 422, {"erro": "tipo de evento inválido"}

    evento_id = evento.get("evento_id")
    pedido_id = evento.get("pedido_id")
    total = evento.get("total_centavos")
    if any(not isinstance(valor, str) or not IDENTIFICADOR.fullmatch(valor)
           for valor in (evento_id, pedido_id)):
        return 422, {"erro": "identificadores inválidos"}
    if type(total) is not int or not 1 <= total <= 999_999_999:
        return 422, {"erro": "total_centavos inválido"}

    with closing(sqlite3.connect(caminho)) as banco, banco:
        # A escrita começa a transação antes de consultar um eventual conflito.
        insercao = banco.execute(
            "INSERT INTO pedido VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            (pedido_id, evento_id, total),
        )
        if insercao.rowcount:
            return 201, {"resultado": "registrado", "pedido_id": pedido_id}
        existente = banco.execute(
            "SELECT pedido_id, total_centavos FROM pedido WHERE evento_id = ?",
            (evento_id,),
        ).fetchone()
        if existente == (pedido_id, total):
            return 200, {"resultado": "duplicado", "pedido_id": pedido_id}
        return 409, {"erro": "evento ou pedido em conflito"}


def iniciar_servidor(caminho, segredo, porta):
    criar_banco(caminho)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            self.request.settimeout(5)
            super().setup()

        def responder(self, codigo, resultado):
            corpo = json.dumps(resultado, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def do_POST(self):
            if self.path != "/webhooks/pedidos":
                self.responder(404, {"erro": "rota inexistente"})
                return
            if self.headers.get_content_type() != "application/json":
                self.responder(415, {"erro": "envie application/json"})
                return
            tamanho = self.headers.get("Content-Length", "")
            if not re.fullmatch(r"[0-9]{1,9}", tamanho):
                self.responder(400, {"erro": "Content-Length inválido"})
                return
            if int(tamanho) > LIMITE:
                self.responder(413, {"erro": "corpo excede 8 KiB"})
                return
            corpo = self.rfile.read(int(tamanho))
            if len(corpo) != int(tamanho):
                self.responder(400, {"erro": "corpo incompleto"})
                return
            try:
                codigo, resultado = receber(caminho, corpo, self.headers.get("X-Assinatura", ""), segredo)
            except sqlite3.OperationalError as erro:
                self.log_error("Falha no banco: %s", erro)
                codigo, resultado = 503, {"erro": "armazenamento indisponível"}
            self.responder(codigo, resultado)

    return ThreadingHTTPServer(("127.0.0.1", porta), Handler)


def main():
    parser = argparse.ArgumentParser(description="Receptor local de webhooks de pedidos.")
    parser.add_argument("--porta", type=int, default=8765)
    parser.add_argument("--banco", default="ponte.sqlite3")
    args = parser.parse_args()
    segredo = os.environ.get("PONTE_SEGREDO", "").encode("utf-8")
    if not segredo:
        parser.error("Defina PONTE_SEGREDO antes de iniciar o receptor.")
    with iniciar_servidor(args.banco, segredo, args.porta) as servidor:
        print(f"Receptor em http://127.0.0.1:{servidor.server_port}/webhooks/pedidos", flush=True)
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
