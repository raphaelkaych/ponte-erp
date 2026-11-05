import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

from ponte import assinar, criar_banco, receber


class PonteTest(unittest.TestCase):
    def setUp(self):
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.banco = Path(pasta.name) / "test.sqlite3"
        self.segredo = b"segredo-de-teste"
        criar_banco(self.banco)

    def enviar(self, **alteracoes):
        evento = {"evento_id": "evt-1", "pedido_id": "pd-1", "tipo": "pedido.criado", "total_centavos": 500}
        evento.update(alteracoes)
        corpo = json.dumps(evento).encode("utf-8")
        return receber(self.banco, corpo, assinar(corpo, self.segredo), self.segredo)[0]

    def test_reenvio_concorrente_cria_um_unico_pedido(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            codigos = list(pool.map(lambda _: self.enviar(), range(6)))
        self.assertEqual(sorted(codigos), [200] * 5 + [201])
        with closing(sqlite3.connect(self.banco)) as banco:
            self.assertEqual(banco.execute("SELECT COUNT(*) FROM pedido").fetchone()[0], 1)

    def test_evento_ou_pedido_em_conflito(self):
        self.assertEqual(self.enviar(), 201)
        self.assertEqual(self.enviar(total_centavos=501), 409)
        self.assertEqual(self.enviar(evento_id="evt-2"), 409)

    def test_assinatura_e_payload_invalidos(self):
        self.assertEqual(receber(self.banco, b"{}", "incorreta", self.segredo)[0], 401)
        corpo = b"{"
        self.assertEqual(receber(self.banco, corpo, assinar(corpo, self.segredo), self.segredo)[0], 400)
        self.assertEqual(self.enviar(total_centavos=True), 422)
        self.assertEqual(self.enviar(pedido_id=""), 422)


if __name__ == "__main__":
    unittest.main()
