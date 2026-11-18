# Instruções para agentes

Receptor de webhooks em Python com HMAC-SHA256 e SQLite, parte do portfólio de Raphael Kaych. O [README](README.md) é a documentação vigente; a demo no navegador e o estudo de caso ficam no repositório [farol-de-integracoes](https://github.com/raphaelkaych/farol-de-integracoes) (`/demos/ponte-erp` e `/projetos/ponte-erp`).

## Comandos

Python 3.10 ou superior, só a biblioteca padrão.

```sh
python -m unittest -v
```

Para a demonstração manual, defina `PONTE_SEGREDO` com um valor de teste no ambiente, rode `python ponte.py` e, em outro terminal, `python enviar_exemplo.py`.

## Regras

- Preserve o contrato `pedido.criado` e os retornos documentados: `201`, `200` para reenvio idêntico, `409` para conflito e `401` para assinatura ausente ou incorreta.
- A deduplicação e a gravação do pedido acontecem na mesma transação. Não troque isso por verificação prévia fora da transação.
- O segredo vem do ambiente. Nunca grave segredo real em código, README, testes ou logs; `.env` fica fora do Git.
- Mudança de comportamento exige teste em `test_ponte.py` e revisão do README e do estudo de caso no portfólio.
- Trabalhe em branch própria e abra PR para `main`.
