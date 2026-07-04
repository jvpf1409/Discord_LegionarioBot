# 🛡️ Bot de Actividades — Hermandad de World of Warcraft

Bot de Discord en Python (discord.py) para gestionar eventos/actividades de tu hermandad:
inscripciones con botones y formularios (Modals), cierre de inscripciones, generación
balanceada de equipos y registro de ganadores.

## Estructura del proyecto

```
wow-bot/
├── main.py                 # Punto de entrada del bot
├── cogs/
│   ├── eventos.py           # Comandos slash (/evento crear, cerrar, etc.)
│   └── vistas.py            # Botones persistentes + Modal de inscripción
├── utils/
│   ├── storage.py           # Persistencia en JSON
│   └── equipos.py           # Algoritmo de balanceo de equipos por rol
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
```

> `GUILD_ID` hace que los comandos slash aparezcan al instante en ese servidor.
> Si lo dejas vacío, la sincronización global puede tardar hasta ~1 hora la primera vez.

## 5. Ejecutar el bot

```bash
python main.py
```

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
| `/evento crear titulo descripcion tipo_inscripcion fecha hora canal_publicacion [num_equipos] [imagen] [canal_inscripciones]` | Publica el evento con embed + botones "Inscribirse" y "Darme de baja" |
| `/evento cerrar evento_id` | Cierra inscripciones, deshabilita el botón |
| `/evento generar_equipos evento_id [num_equipos]` | Solo para eventos **individuales**: genera y publica los equipos balanceados |
| `/evento registrar_ganador evento_id numero_equipo` | Marca el equipo ganador y finaliza el evento |
| `/evento listar [estado]` | Lista eventos del servidor (abiertos/cerrados/finalizados) |
| `/evento cancelar evento_id` | Cancela el evento por completo |

### Tipos de inscripción

- **Individual**: cada persona se inscribe con un formulario de un solo campo (nombre de
  personaje). Al cerrar inscripciones, el oficial usa `/evento generar_equipos` para
  repartir a los inscritos de forma balanceada entre `num_equipos` equipos.
- **Grupal**: cada inscripción registra un equipo completo ya formado. El formulario
  aparece en dos pasos: primero el nombre del equipo; al enviarlo aparece un botón
  **➡️ Continuar** (Discord no permite abrir un modal directamente desde otro modal),
  que abre el segundo formulario con los 5 roles (Tank, Healer, DPS x3). No se pide
  `num_equipos` al crear el evento: se pueden inscribir equipos sin límite hasta que se
  cierren las inscripciones. `/evento generar_equipos` no aplica porque los equipos ya
  quedan fijos desde la inscripción.

### Fecha, hora e imagen

Al crear el evento se piden `fecha` (formato `DD/MM/AAAA`) y `hora` (formato 24h `HH:MM`),
interpretadas con la zona horaria de `ZONA_HORARIA` (variable de entorno, por defecto
`America/Mexico_City`). Se muestran en el embed con el formato dinámico de Discord
(`📅 Fecha y hora`), que cada usuario ve automáticamente en su propio huso horario, junto
con el tiempo relativo ("en 3 días" / "hace 3 días"). También se puede adjuntar una
`imagen` (banner, logo del jefe, etc.) que se muestra al final del embed.

### Flujo típico

1. Un oficial ejecuta `/evento crear titulo:"Mítico+ semanal" descripcion:"Trae tu build de M+" tipo_inscripcion:Individual num_equipos:2 canal_publicacion:#eventos canal_inscripciones:#inscripciones-log`.
2. El bot publica el embed con botones en el canal elegido. Cada inscripción/baja se
   anuncia también en `canal_inscripciones` si se configuró, además de actualizar el embed.
3. Cuando ya no se aceptan más inscritos: `/evento cerrar evento_id:1`.
4. Si el evento es individual, el oficial genera los equipos: `/evento generar_equipos evento_id:1`.
   Si es grupal, los equipos ya están formados desde la inscripción.
5. Al terminar la actividad: `/evento registrar_ganador evento_id:1 numero_equipo:2`.
   El bot anuncia al equipo ganador y marca el evento como finalizado.

## 7. Persistencia y reinicios

Toda la información se guarda en `data/eventos.json`. Al reiniciar el bot, `main.py`
vuelve a registrar automáticamente los botones de los eventos que sigan abiertos o
cerrados (pero no finalizados), por lo que los botones **no se rompen** tras un reinicio
o caída del bot.

## 8. Personalización rápida

- **Restringir a un rol de oficial en vez de "Gestionar servidor":**
  cambia el decorador `es_organizador()` en `cogs/eventos.py` por
  `app_commands.checks.has_role("Oficial")`.
- **Añadir más roles de WoW o especializaciones:** ajusta `utils/equipos.py`
  (`normalizar_rol`) y el campo `rol` del Modal en `cogs/vistas.py`.
- **Cambiar el máximo de equipos:** modifica el `app_commands.Range[int, 1, 20]`
  en los comandos correspondientes.

## 9. Migrar a una base de datos real (opcional)

Si tu hermandad crece mucho, `utils/storage.py` está aislado a propósito: puedes
reemplazar sus funciones internas por llamadas a SQLite/PostgreSQL sin tocar el resto
del bot, ya que los cogs solo dependen de las funciones públicas (`crear_evento`,
`obtener_evento`, `agregar_participante`, etc.).
