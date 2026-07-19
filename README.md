# 🛡️ Bot de Actividades — Hermandad de World of Warcraft

Bot de Discord en Python (discord.py) para gestionar eventos/actividades de tu hermandad:
inscripciones con botones y formularios (Modals), cierre de inscripciones y registro
de ganadores para eventos grupales.

## Estructura del proyecto

```
wow-bot/
├── main.py                 # Punto de entrada del bot
├── cogs/
│   ├── eventos.py           # Comandos slash (/evento crear, cerrar, etc.)
│   └── vistas.py            # Botones persistentes + Modal de inscripción
├── utils/
│   ├── storage.py           # Persistencia en JSON
├── data/
│   └── eventos.json          # Base de datos (se genera/actualiza sola)
├── requirements.txt
└── .env.example
```

## 1. Requisitos previos

- Python 3.10 o superior
- Una aplicación de Discord con su Bot creado en https://discord.com/developers/applications

## 2. Crear el bot en Discord

1. Entra al [Portal de Desarrolladores de Discord](https://discord.com/developers/applications) y crea una nueva aplicación.
2. Ve a la pestaña **Bot** → **Reset Token** → copia el token (lo necesitarás en el paso 4).
3. En **Bot**, activa el intent **Server Members Intent** si más adelante quieres validar roles del gremio (no es obligatorio para lo que incluye este bot).
4. Ve a **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Permisos del bot: `Send Messages`, `Embed Links`, `Read Message History`, `Use Slash Commands`, `Manage Messages` (para editar el mensaje del evento).
5. Copia la URL generada y ábrela en el navegador para invitar el bot a tu servidor.

## 3. Instalación

```bash
cd wow-bot
python -m venv venv
source venv/bin/activate      # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 4. Configuración

Copia `.env.example` a `.env` y rellena tu token:

```bash
cp .env.example .env
```

```
DISCORD_TOKEN=tu_token_aqui
GUILD_ID=tu_id_de_servidor   # opcional, recomendado durante pruebas
CANAL_AVISOS_ID=id_del_canal_general       # opcional
ROL_AVISOS_ID=id_del_rol_legionarios       # opcional
```

Si configuras `CANAL_AVISOS_ID`, al crear un evento o raid el bot publicará
automáticamente un aviso con el enlace directo a la publicación. Si además
configuras `ROL_AVISOS_ID`, mencionará ese rol (por ejemplo, Legionarios).
El mismo canal y rol reciben un único recordatorio 30 minutos antes del inicio.

> `GUILD_ID` hace que los comandos slash aparezcan al instante en ese servidor.
> Si lo dejas vacío, la sincronización global puede tardar hasta ~1 hora la primera vez.

## 5. Ejecutar el bot

```bash
python main.py
```

Durante el desarrollo puedes usar recarga automática. El proceso del bot se
reinicia cada vez que guardas un archivo `.py` o modificas `.env`:

```bash
python scripts/dev.py
```

Pulsa `Ctrl+C` para detenerlo. No se necesita ngrok porque el bot inicia una
conexión saliente hacia Discord; no recibe webhooks HTTP en este proyecto.

Si todo va bien verás algo como:
```
✅ Conectado como HermandadBot#1234 — 6 comandos sincronizados.
```

## 6. Comandos disponibles

Todos son comandos slash bajo el grupo `/evento`. Los que crean o modifican eventos
requieren el permiso **Gestionar servidor** (puedes cambiar esto en `cogs/eventos.py`,
función `es_organizador()`, por ejemplo para exigir un rol específico como "Oficial").

| Comando | Descripción |
|---|---|
| `/evento crear titulo tipo_inscripcion fecha hora canal_publicacion [imagen] [canal_inscripciones]` | Abre un formulario para la descripción y publica el evento con embed + botones |
| `/evento cerrar evento_id` | Cierra inscripciones, deshabilita el botón |
| `/evento registrar_ganador evento_id [ganador] [numero_equipo]` | Marca al participante o equipo ganador y finaliza el evento |
| `/evento listar [estado]` | Lista eventos del servidor (abiertos/cerrados/finalizados) |
| `/evento cancelar evento_id` | Cancela el evento por completo |

### Tipos de inscripción

- **Individual**: cada persona se inscribe con un formulario de un solo campo (nombre de
  personaje). El evento conserva una lista simple de participantes.
- **Grupal**: cada inscripción registra un equipo completo ya formado. El formulario
  aparece en dos pasos: primero el nombre del equipo; al enviarlo aparece un botón
  **➡️ Continuar** (Discord no permite abrir un modal directamente desde otro modal),
  que abre el segundo formulario con los 5 roles (Tank, Healer, DPS x3). No se pide
  un límite de equipos: se pueden inscribir equipos hasta que se cierren las
  inscripciones. Los equipos quedan fijos desde la inscripción.

### Fecha, hora e imagen

Al crear el evento se piden `fecha` (formato `DD/MM/AAAA`) y `hora` (formato 24h `HH:MM`),
interpretadas con la zona horaria de `ZONA_HORARIA` (variable de entorno, CST/UTC-6 por
defecto). Se muestran en el embed con el formato dinámico de Discord (`📅 Fecha y hora`),
que cada usuario ve automáticamente en su propio huso horario, junto con el tiempo
relativo ("en 3 días" / "hace 3 días"). También se puede adjuntar una `imagen` (banner,
logo del jefe, etc.) que se muestra al final del embed.

### La descripción se pide en un formulario aparte

Los parámetros de un slash command son cajas de texto de una sola línea — Discord no
permite saltos de línea ahí. Por eso, al ejecutar `/evento crear`, después de llenar los
demás campos se abre un formulario (modal) con un campo de texto tipo párrafo para la
**descripción**, que sí admite varias líneas y párrafos como los ves en Discord normalmente.

### Flujo típico

1. Un oficial ejecuta `/evento crear titulo:"Mítico+ semanal" tipo_inscripcion:Individual fecha:30/06/2026 hora:23:00 canal_publicacion:#eventos canal_inscripciones:#inscripciones-log`.
2. Se abre un formulario para escribir la descripción (con saltos de línea) y al enviarlo
   el bot publica el embed con botones en el canal elegido. Cada inscripción/baja se
   anuncia también en `canal_inscripciones` si se configuró, además de actualizar el embed.
3. Cuando ya no se aceptan más inscritos: `/evento cerrar evento_id:1`.
4. Si es grupal, los equipos ya están formados desde la inscripción.
5. Al terminar una actividad individual, usa `/evento registrar_ganador evento_id:1 ganador:@usuario`.
   Para una grupal, usa `/evento registrar_ganador evento_id:1 numero_equipo:2`.

## 7. Persistencia y reinicios

Al reiniciar el bot, `main.py` vuelve a registrar automáticamente los botones de los
eventos que sigan abiertos o cerrados (pero no finalizados), por lo que los botones
**no se rompen** tras un reinicio o caída del bot — siempre que los datos del evento
sigan existiendo (ver siguiente sección).

### Dónde se guardan los datos

- **Sin `DATABASE_URL` configurada** (por ejemplo, corriendo el bot en tu máquina): los
  eventos se guardan en `data/eventos.json`. Cómodo para probar, pero **no sirve para
  producción en Render**: su filesystem no es persistente, así que ese archivo se resetea
  a lo que esté commiteado en git cada vez que se hace un deploy nuevo, perdiendo
  cualquier evento creado después del último commit.
- **Con `DATABASE_URL` configurada**: los eventos se guardan en esa base de datos Postgres
  en vez del archivo JSON, y sobreviven a cualquier deploy. **Es obligatorio configurarla
  en Render** para no perder datos reales de tu hermandad.

Cómo configurarla (gratis):
1. Crea una cuenta en [Supabase](https://supabase.com) o [Neon](https://neon.tech) (ambos
   tienen un plan Postgres gratis permanente) y crea un proyecto/base de datos nueva.
2. Copia el connection string (algo como
   `postgresql://usuario:password@host:5432/basededatos`).
3. En Render: ve a tu servicio → **Environment** → agrega la variable `DATABASE_URL` con
   ese valor, y vuelve a desplegar.
4. En tu máquina, **no** definas `DATABASE_URL` en tu `.env` local (déjala vacía) para
   seguir probando con el archivo JSON — así tu entorno de pruebas nunca toca los datos
   reales de producción.

El bot detecta automáticamente cuál usar: si `DATABASE_URL` existe, usa Postgres
(`utils/storage_pg.py`); si no, usa el archivo JSON (`utils/storage_json.py`). Ambos
implementan las mismas funciones, así que el resto del código no distingue cuál está activo.

## 8. Personalización rápida

- **Restringir a un rol de oficial en vez de "Gestionar servidor":**
  cambia el decorador `es_organizador()` en `cogs/eventos.py` por
  `app_commands.checks.has_role("Oficial")`.
- **Modificar la composición de equipos grupales:** ajusta los campos de
  `EquipoRosterModal` en `cogs/vistas.py`.

## 9. Base de datos (ya integrado)

Ver sección 7: `utils/storage.py` elige automáticamente entre Postgres
(`utils/storage_pg.py`, producción) y JSON local (`utils/storage_json.py`, pruebas)
según exista o no `DATABASE_URL`. Los cogs solo dependen de las funciones públicas
(`crear_evento`, `obtener_evento`, `agregar_participante`, etc.), así que si más adelante
quieres cambiar de proveedor de base de datos, solo se toca `utils/storage_pg.py`.
