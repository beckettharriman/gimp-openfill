# Security policy

## Supported versions

Security fixes go into the current OpenFill code for GIMP 3 (the
`gimp3-port` line and the releases made from it).

## Reporting a vulnerability

Please report security problems privately through GitHub's private
vulnerability reporting: open the repository's **Security** tab and choose
**Report a vulnerability**. Do not open a public issue or pull request for it.

Include what you found, how to reproduce it, the affected version or commit,
and your operating system and GIMP version. Never include your Hugging Face
token or a full `config.json`; if a token was exposed, revoke it at
https://huggingface.co/settings/tokens first.

What the plug-in trusts, what it validates and where it stores data is
described in [docs/security.md](docs/security.md). That includes the live model
search (Hugging Face and Civitai, `hub-cache.json`, `hub-selected.json`) and the
checksum policy for models that publish no SHA-256.
