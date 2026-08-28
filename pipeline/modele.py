#!/usr/bin/env python3
"""Le client du modèle, construit au même endroit pour tout le pipeline.

Pourquoi ce fichier existe : sur Render, `api.anthropic.com` se résout en IPv6
(`2607:6bc0::10`) alors que le conteneur n'a pas de sortie IPv6. La bibliothèque
échoue alors sur « APIConnectionError: Connection error. » — un message qui ne
dit ni que c'est le réseau, ni que c'est l'IPv6. L'IPv4 du même hôte répond très
bien. On force donc la pile IPv4 en fixant l'adresse locale de sortie.

Diagnostic reproductible depuis le conteneur :

    getent hosts api.anthropic.com          → 2607:6bc0::10   (IPv6 seulement)
    socket.connect(('160.79.104.10', 443))  → IPv4 OK
"""
import os

TIMEOUT = 600.0
RETRIES = 1


def client(timeout=TIMEOUT, max_retries=RETRIES):
    import anthropic
    import httpx

    # WB_IPV6=1 pour un hôte qui n'aurait que de l'IPv6 : on ne force plus rien.
    if os.environ.get("WB_IPV6") == "1":
        return anthropic.Anthropic(timeout=timeout, max_retries=max_retries)

    reseau = httpx.Client(transport=httpx.HTTPTransport(local_address="0.0.0.0"),
                          timeout=timeout)
    return anthropic.Anthropic(http_client=reseau, max_retries=max_retries)
