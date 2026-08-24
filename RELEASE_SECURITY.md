# Проверка релизов

Публикуемые релизы Zapret Hub собираются из подписанного Git-тега. Для каждого
релиза GitHub Actions публикует:

- `SHA256SUMS.txt` — SHA-256 для установщика, Portable ZIP и WinGet-манифестов;
- `SHA256SUMS.txt.asc` — detached GPG-подпись этого манифеста;
- `release-signing-key.asc` — открытый ключ для проверки подписи.

Доверенный fingerprint ключа:

`4001 5491 B3A6 3D77 7855 FEC0 8DA8 2B54 BDED 31AE`

Пример проверки в PowerShell с установленным GnuPG:

```powershell
Invoke-WebRequest `
  -Uri https://github.com/klondike0x/Zapret-Hub/releases/download/vX.Y.Z/release-signing-key.asc `
  -OutFile release-signing-key.asc
gpg --show-keys --fingerprint release-signing-key.asc
gpg --import release-signing-key.asc
gpg --verify SHA256SUMS.txt.asc SHA256SUMS.txt
sha256sum -c SHA256SUMS.txt
```

Перед публикацией workflow проверяет подписанный тег, отказывается изменять
уже существующий релиз, создаёт draft, загружает артефакты, скачивает их обратно
через GitHub и повторно проверяет подпись и хэши. Только после этого draft
становится опубликованным релизом. Это сохраняет неизменяемость релизного
процесса: повторная публикация того же тега запрещена.

Для нового релиза создаётся подписанный annotated tag, например:

```powershell
git tag -s vX.Y.Z -m "Zapret Hub X.Y.Z"
git push origin vX.Y.Z
```
Приватный ключ не хранится в репозитории. Для публикации администратор должен
настроить в GitHub Actions Secrets:

- `RELEASE_GPG_PRIVATE_KEY` — ASCII-armored private key;
- `RELEASE_GPG_PASSPHRASE` — пароль ключа.

Ключ в `release-signing-key.asc` должен соответствовать fingerprint выше.
