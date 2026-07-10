# Íconos personalizados

Pon aquí las imágenes de tus íconos (`.png`, `.jpg` o `.gif`). El bot las sube
automáticamente como "application emojis" (le pertenecen al bot, no a un
servidor de Discord puntual) la primera vez que arranca después de agregarlas,
y de ahí en adelante las reutiliza sin volver a subirlas.

El **nombre del archivo** (sin extensión) es el nombre del ícono en el código.
Para los roles de raid, usa exactamente estos nombres:

- `tank.png`
- `healer.png`
- `melee.png`
- `ranged.png`

Reglas del nombre (las exige Discord): solo letras, números y guion bajo,
entre 2 y 32 caracteres, sin espacios ni tildes.

Si no agregas un archivo para alguno de estos roles, el bot sigue funcionando
normal y usa el emoji de reserva (🛡️ ➕ ⚔️ 🏹) definido en `utils/wow_data.py`.

Después de agregar o cambiar un archivo, reinicia el bot para que lo detecte
y lo suba.
