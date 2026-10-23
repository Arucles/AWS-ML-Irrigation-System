# Servicios systemd de usuario

El sistema corre en la Raspberry Pi con tres servicios gestionados por systemd (modo usuario,
con `loginctl enable-linger aru` para que sigan vivos al cerrar el SSH):

| Servicio | Qué hace | Reinicio |
|---|---|---|
| `riego-api` | `app.py` — Flask en el puerto 5000 (`/health`, `/predict`) | automático |
| `riego-sensor` | `ejecutar_sensor.py` — lee el ADS1115 y escribe el CSV cada 120 min | automático |
| `riego-post` | `post.py` — vigila el CSV y consulta la API | automático |

## Instalación (una sola vez, en la Pi)

Los unit files describen la configuración ya aplicada. Para recrearlos, adapta
`WorkingDirectory` y la ruta de `venv/bin/python` a tu instalación.

```bash
# El venv necesita ver python3-rpi.gpio (paquete del sistema) para blinka:
echo "/usr/lib/python3/dist-packages" > \
  venv/lib/python3.13/site-packages/system_dist_packages.pth

# El webhook se guarda fuera de git (está en .gitignore)
printf 'DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...\n' > .env
chmod 600 .env

systemctl --user daemon-reload
systemctl --user enable --now riego-api riego-sensor riego-post
sudo loginctl enable-linger aru   # sobrevive al cierre de la sesión SSH
```

## Operación

```bash
systemctl --user status riego-api riego-sensor riego-post
systemctl --user restart riego-sensor     # tras recalibrar o cambiar TIPO_PLANTA
journalctl --user -u riego-sensor -f      # ver lecturas en vivo (requiere journald persistente)
```

## Notas de memoria (Pi Zero 2 W, 415 MB útiles)

- `app.py` arranca con `debug=False` salvo que se exporte `DEBUG=1`. El modo debug de Werkzeug
  lanza un segundo proceso (~87 MB) y en esta Pi provoca swap.
- `riego-sensor` tiene `MemoryMax=96M` como red de seguridad.
- `TIPO_PLANTA` está fijado en el código (`ejecutar_sensor.py`), no por variable de entorno.
