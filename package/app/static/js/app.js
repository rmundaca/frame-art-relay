'use strict';

/* ------------------------------------------------------------------ i18n */

const I18N = {
    es: {
        locale: 'es-ES',
        appName: 'Frame Art Relay',
        tabAlbums: 'Álbumes', tabTvs: 'Televisores', tabSchedule: 'Horario',
        settings: 'Ajustes', close: 'Cerrar', cancel: 'Cancelar', save: 'Guardar', delete: 'Eliminar',
        edit: 'Editar', back: 'Volver', saved: 'Cambios guardados', deleted: 'Eliminado',
        // Albums
        emptyAlbumsTitle: 'Aún no hay álbumes', emptyAlbumsText: 'Crea álbumes con imágenes de carpetas del NAS o de álbumes compartidos de iCloud.',
        newAlbum: 'Nuevo álbum', name: 'Nombre', interval: 'Cambiar cada', order: 'Orden',
        shuffle: 'Aleatorio', sequential: 'Secuencial', matte: 'Marco',
        rotation: 'Rotación', display: 'Presentación', help: 'Ayuda',
        albumMeta: '{n} de {total} imágenes', noSources: 'Sin carpetas',
        sources: 'Carpetas', addFolder: 'Añadir carpeta', subfolders: 'con subcarpetas',
        images: 'Imágenes', rescan: 'Reescanear', rescanned: 'Carpetas reescaneadas',
        noImages: 'No hay imágenes en las carpetas del álbum.',
        deleteAlbum: 'Eliminar álbum', deleteAlbumMsg: 'Se quitará de todas las franjas y sus fotos se borrarán de los televisores. Las fotos del NAS no se tocan.',
        deleteSource: 'Quitar carpeta', deleteSourceMsg: 'Sus imágenes dejarán de formar parte del álbum.',
        chooseFolder: 'Elegir carpeta', useFolder: 'Usar esta carpeta', folderImages: '{n} imágenes en esta carpeta',
        includeSubfolders: 'Incluir subcarpetas', up: 'Subir un nivel', roots: 'Carpetas permitidas',
        folderAdded: 'Carpeta añadida',
        addIcloud: 'Añadir iCloud', icloudTitle: 'Álbum compartido de iCloud', icloudUrl: 'Enlace del álbum',
        icloudHelp: 'En Fotos, abre las opciones de compartir del álbum, permite "Cualquier persona con el enlace" o activa "Sitio web público" y copia el enlace.',
        icloudAdded: 'Descargando las fotos de iCloud...', downloading: 'Descargando...',
        composition: 'Composiciones',
        dateStamp: 'Fecha (iCloud)',
        singleFit: 'Fotos sueltas',
        fitCrop: 'Llenar pantalla',
        fitWhole: 'Completas',
        background: 'Fondo',
        bgPaper: 'Papel',
        bgBlur: 'Desenfocado',
        subjectDetection: 'Recorte inteligente',
        subjectNeedsKey: 'El recorte inteligente necesita una clave de Gemini en Ajustes.',
        outputMeta: '{photos} fotos · {total} imágenes para el TV',
        megabytes: '{n} MB', onTv: '{size} en el TV',
        compositions: 'Composiciones', regenerate: 'Regenerar', regenerating: 'Generando composiciones...',
        composeWaiting: 'Agrupando las fotos...', composePending: 'Preparando {n} composiciones...',
        noCompositions: 'Ninguna foto tiene una combinación adecuada: todas se muestran por separado.',
        originals: 'Fotos originales',
        albumHelp: [
            ['Cambiar cada', 'Cada cuánto cambia la imagen. La cambia la app entre las fotos de este álbum, solo con la pantalla encendida.'],
            ['Orden', 'Aleatorio baraja las imágenes; Secuencial las muestra por nombre de archivo.'],
            ['Fotos sueltas', 'Llenar pantalla recorta cada foto a 16:9. Completas muestra enteras las verticales y panorámicas sobre el fondo; las horizontales que casi llenan la pantalla se siguen recortando.'],
            ['Composiciones', 'Agrupa dos o tres fotos en una sola imagen, como una hoja de álbum. Esas fotos ya no se muestran por separado. Al borrar una composición en la galería del TV, sus fotos se excluyen del álbum.'],
            ['Fecha (iCloud)', 'Añade abajo a la derecha la fecha en que se tomó cada foto de iCloud (AAAA-MM-DD). Las fotos del NAS no cambian.'],
            ['Recorte inteligente', 'Pregunta a Gemini dónde están las personas y animales para no cortarlos. Envía a Google una copia reducida de cada foto, sin ubicación ni metadatos. Requiere una clave en Ajustes.'],
            ['Fondo', 'Rellena el espacio libre de las composiciones y de las fotos completas. Desenfocado usa la propia foto.'],
            ['Marco', 'Paspartú que dibuja el TV alrededor de la imagen.'],
            ['Imágenes', 'Toca una imagen para excluirla o incluirla (máximo {max} por álbum). Las composiciones se rehacen solas; toca una para ver sus fotos.'],
            ['Espacio en el TV', 'MB que ocupa el álbum en los televisores. Sus fotos se quedan en el TV al cambiar de franja, para no volver a subirlas, y solo se borran al eliminar el álbum.'],
        ],
        page: 'Composición', pageMembers: 'Fotos de esta composición', openFull: 'Ver a tamaño real',
        pageStatus: { pending: 'Preparando', updating: 'Actualizando', error: 'Error' },
        matteStyle: { none: 'Sin marco', modern: 'Moderno', shadowbox: 'Caja' },
        matteColor: {
            black: 'negro', neutral: 'neutro', antique: 'antiguo', warm: 'cálido', polar: 'polar', sand: 'arena',
            seafoam: 'espuma', sage: 'salvia', burgandy: 'burdeos', navy: 'marino',
        },
        minutes: '{n} min', hours: '{n} h', oneDay: '1 día', days: '{n} días',
        // TVs
        emptyTvsTitle: 'Aún no hay televisores', emptyTvsText: 'Añade tu Samsung The Frame por su IP.',
        newTv: 'Añadir televisor', host: 'Dirección IP', model: 'Modelo', mac: 'MAC', state: 'Estado',
        tvAdded: 'Televisor añadido',
        states: {
            art: 'Modo arte', tv: 'En uso', standby: 'Apagándose', offline: 'Apagado', on: 'Sin emparejar',
            unknown: 'Sin datos',
        },
        nowShowing: 'Ahora: {name}', noActiveSlot: 'Sin franja activa', disabled: 'Pausado',
        pairTitle: 'Falta emparejar',
        pairHelp: 'Enciende el TV en modo TV (no en modo arte), pulsa Emparejar y acepta el aviso en pantalla. Para que no vuelva a preguntar: Ajustes > General > Administrador de conexión de dispositivos > Notificación de acceso > Solo la primera vez.',
        pair: 'Emparejar', pairing: 'Esperando al TV...', paired: 'Emparejado',
        refresh: 'Actualizar estado', syncNow: 'Sincronizar ahora', syncQueued: 'Sincronización en marcha',
        gallery: 'Galería del TV', uploaded: 'Subidas por la app', lastError: 'Último error',
        storageUsed: 'Espacio usado',
        storageWarn: 'La app ha subido {used} a {name}, más de {limit}. Elimina los álbumes que no uses para liberar espacio en el TV.',
        enabled: 'Activo', pause: 'Pausar', resume: 'Reanudar',
        deleteTv: 'Eliminar televisor', deleteTvMsg: 'Se borran sus franjas. Las fotos del TV se quedan.',
        galleryHelp: 'La rotación solo usa las fotos del álbum activo. Las de otros álbumes se quedan en el TV hasta que eliminas el álbum. Las que borres aquí y vengan de un álbum quedan excluidas de él.',
        galleryEmpty: 'No hay fotos en "Mis fotos".', fromApp: 'App',
        deleteSelected: 'Borrar seleccionadas ({n})', deletePhotos: 'Borrar fotos del TV',
        deletePhotosMsg: 'Se borrarán {n} fotos del televisor.', photosDeleted: '{n} fotos borradas',
        deletePagesMsg: 'Incluye {n} composiciones: todas sus fotos quedarán excluidas del álbum para que no se vuelvan a generar. Los archivos originales no se borran.',
        loadingGallery: 'Leyendo el TV...',
        // Schedule
        emptyScheduleTitle: 'Sin franjas horarias', emptyScheduleText: 'Define qué álbum se muestra en cada TV y cuándo.',
        needTvAndAlbum: 'Primero añade un televisor y un álbum.',
        newSlot: 'Añadir franja', editSlot: 'Franja horaria', tv: 'Televisor', album: 'Álbum', daysLabel: 'Días',
        start: 'Desde', end: 'Hasta', slotEnabled: 'Activa', slotPaused: 'Pausada',
        scheduleHint: 'Fuera de las franjas la rotación se detiene y el TV queda en modo arte.',
        everyDay: 'Todos los días', weekdays: 'Lunes a viernes', weekends: 'Fines de semana',
        dayShort: ['L', 'M', 'X', 'J', 'V', 'S', 'D'],
        deleteSlot: 'Eliminar franja', deleteSlotMsg: 'El TV dejará de mostrar este álbum en ese horario.',
        // Settings
        theme: 'Tema', themeOpt: { system: 'Sistema', light: 'Claro', dark: 'Oscuro' },
        language: 'Idioma', version: 'Versión {v}',
        aiTitle: 'Gemini', aiKey: 'Clave de la API', aiModel: 'Modelo', aiLimit: 'Consultas por día como máximo',
        aiKeySet: 'Configurada (termina en {hint})', aiKeyNone: 'Sin configurar', aiUsage: '{n} consultas hoy',
        aiKeyPlaceholder: 'Pega la clave para cambiarla', aiTest: 'Probar', aiTestOk: 'Gemini responde correctamente.',
        aiRemove: 'Quitar la clave',
        settingsHelp: [
            ['Tema e idioma', 'Se guardan solo en este dispositivo.'],
            ['Carpetas permitidas', 'Carpetas del NAS que se pueden añadir a los álbumes. Se definen en config.yaml (media.roots).'],
            ['Gemini', 'Solo lo usan los álbumes con Recorte inteligente. La clave se guarda en el NAS y no se vuelve a mostrar. El límite diario evita costes inesperados.'],
        ],
        err: {
            network: 'No se pudo contactar con el servidor.',
            not_found: 'Ya no existe.',
            invalid_name: 'Escribe un nombre.',
            invalid_host: 'Escribe una IP válida.',
            tv_unreachable: 'No se encontró el TV en esa IP. Comprueba que esté encendido.',
            not_a_frame_tv: 'Ese televisor no es un The Frame.',
            pair_failed: 'No se pudo emparejar. Pon el TV en modo TV y acepta el aviso.',
            tv_not_paired: 'Primero empareja el TV.',
            tv_unavailable: 'El TV no responde. Debe estar en modo arte.',
            tv_busy: 'El TV está ocupado con otra operación. Inténtalo en un momento.',
            tv_timeout: 'El TV tardó demasiado en responder.',
            thumbnail_failed: 'No se pudo leer la miniatura.',
            invalid_content_ids: 'Selección no válida.',
            invalid_path: 'Esa carpeta no existe.',
            path_not_allowed: 'Esa carpeta está fuera de las permitidas.',
            source_exists: 'Esa carpeta ya está en el álbum.',
            invalid_matte: 'Marco no válido.',
            invalid_interval: 'Intervalo no válido.',
            invalid_days: 'Elige al menos un día.',
            invalid_time: 'Hora no válida.',
            invalid_time_range: 'La hora de inicio y la de fin no pueden ser iguales.',
            slot_overlap: 'Se solapa con otra franja de ese televisor.',
            invalid_icloud_url: 'Pega el enlace público del álbum (photos.icloud.com/shared/album/... o icloud.com/sharedalbum/#...).',
            icloud_album_not_public: 'El álbum no es público o el enlace caducó. Permite "Cualquier persona con el enlace" o activa "Sitio web público".',
            icloud_unreachable: 'No se pudo contactar con iCloud.',
            invalid_composition_mode: 'Modo de composición no válido.',
            invalid_background: 'Fondo no válido.',
            invalid_single_fit: 'Ajuste de fotos sueltas no válido.',
            gemini_key_missing: 'Falta la clave de Gemini. Configúrala en Ajustes.',
            gemini_key_invalid: 'Gemini rechazó la clave.',
            gemini_unreachable: 'No se pudo contactar con Gemini. Se reintentará; mientras tanto se recorta al centro.',
            gemini_response_invalid: 'Gemini devolvió una respuesta no válida.',
            gemini_quota_exceeded: 'Se alcanzó el límite de consultas a Gemini. Se continuará más tarde.',
            invalid_gemini_model: 'Ese modelo de Gemini no existe.',
            invalid_gemini_limit: 'Escribe un límite entre 1 y 100000.',
            composition_source_unavailable: 'Falta una de las fotos de la composición. Reescanea el álbum.',
            composition_render_failed: 'No se pudo generar la composición: alguna foto está dañada o es demasiado grande.',
            generic: 'Algo salió mal. Inténtalo de nuevo.',
        },
    },
    en: {
        locale: 'en-GB',
        appName: 'Frame Art Relay',
        tabAlbums: 'Albums', tabTvs: 'TVs', tabSchedule: 'Schedule',
        settings: 'Settings', close: 'Close', cancel: 'Cancel', save: 'Save', delete: 'Delete',
        edit: 'Edit', back: 'Back', saved: 'Changes saved', deleted: 'Deleted',
        emptyAlbumsTitle: 'No albums yet', emptyAlbumsText: 'Create albums with images from NAS folders or iCloud shared albums.',
        newAlbum: 'New album', name: 'Name', interval: 'Change every', order: 'Order',
        shuffle: 'Shuffle', sequential: 'In order', matte: 'Matte',
        rotation: 'Rotation', display: 'Display', help: 'Help',
        albumMeta: '{n} of {total} images', noSources: 'No folders',
        sources: 'Folders', addFolder: 'Add folder', subfolders: 'with subfolders',
        images: 'Images', rescan: 'Rescan', rescanned: 'Folders rescanned',
        noImages: 'There are no images in the album folders.',
        deleteAlbum: 'Delete album', deleteAlbumMsg: 'It will be removed from every time slot and its photos will be deleted from the TVs. NAS photos are not touched.',
        deleteSource: 'Remove folder', deleteSourceMsg: 'Its images will no longer be part of the album.',
        chooseFolder: 'Choose folder', useFolder: 'Use this folder', folderImages: '{n} images in this folder',
        includeSubfolders: 'Include subfolders', up: 'Up one level', roots: 'Allowed folders',
        folderAdded: 'Folder added',
        addIcloud: 'Add iCloud', icloudTitle: 'iCloud shared album', icloudUrl: 'Album link',
        icloudHelp: 'In Photos, open the album sharing options, allow "Anyone with the Link" or turn on "Public Website", and copy the link.',
        icloudAdded: 'Downloading photos from iCloud...', downloading: 'Downloading...',
        composition: 'Layouts',
        dateStamp: 'Date (iCloud)',
        singleFit: 'Single photos',
        fitCrop: 'Fill screen',
        fitWhole: 'Whole',
        background: 'Background',
        bgPaper: 'Paper',
        bgBlur: 'Blurred',
        subjectDetection: 'Smart crop',
        subjectNeedsKey: 'Smart crop needs a Gemini key in Settings.',
        outputMeta: '{photos} photos · {total} images for the TV',
        megabytes: '{n} MB', onTv: '{size} on the TV',
        compositions: 'Layouts', regenerate: 'Regenerate', regenerating: 'Generating layouts...',
        composeWaiting: 'Grouping photos...', composePending: 'Preparing {n} layouts...',
        noCompositions: 'No photos have a suitable combination: all of them are shown on their own.',
        originals: 'Original photos',
        albumHelp: [
            ['Change every', 'How often the image changes. The app changes it among this album\'s photos, only while the screen is on.'],
            ['Order', 'Shuffle mixes the images; In order shows them by file name.'],
            ['Single photos', 'Fill screen crops each photo to 16:9. Whole shows portrait and panoramic photos uncropped over the background; landscape photos that almost fill the screen are still cropped.'],
            ['Layouts', 'Combines two or three photos into one image, like an album page. Those photos are no longer shown on their own. Deleting a layout from the TV gallery excludes its photos from the album.'],
            ['Date (iCloud)', 'Adds the date each iCloud photo was taken (YYYY-MM-DD) to its lower right corner. NAS photos are not changed.'],
            ['Smart crop', 'Asks Gemini where the people and animals are so crops keep them. Sends Google a reduced copy of each photo, without location or metadata. Needs a key in Settings.'],
            ['Background', 'Fills the free space in layouts and in photos shown whole. Blurred uses the photo itself.'],
            ['Matte', 'Mat border the TV draws around the image.'],
            ['Images', 'Tap an image to exclude or include it (up to {max} per album). Layouts are rebuilt automatically; tap one to see its photos.'],
            ['Space on the TV', 'MB the album takes up on the TVs. Its photos stay on the TV when the slot changes, so they are not uploaded again, and are only deleted when the album is deleted.'],
        ],
        page: 'Layout', pageMembers: 'Photos in this layout', openFull: 'View full size',
        pageStatus: { pending: 'Preparing', updating: 'Updating', error: 'Error' },
        matteStyle: { none: 'No matte', modern: 'Modern', shadowbox: 'Shadowbox' },
        matteColor: {
            black: 'black', neutral: 'neutral', antique: 'antique', warm: 'warm', polar: 'polar', sand: 'sand',
            seafoam: 'seafoam', sage: 'sage', burgandy: 'burgundy', navy: 'navy',
        },
        minutes: '{n} min', hours: '{n} h', oneDay: '1 day', days: '{n} days',
        emptyTvsTitle: 'No TVs yet', emptyTvsText: 'Add your Samsung The Frame by its IP address.',
        newTv: 'Add TV', host: 'IP address', model: 'Model', mac: 'MAC', state: 'Status',
        tvAdded: 'TV added',
        states: {
            art: 'Art mode', tv: 'In use', standby: 'Turning off', offline: 'Off', on: 'Not paired',
            unknown: 'No data',
        },
        nowShowing: 'Now: {name}', noActiveSlot: 'No active slot', disabled: 'Paused',
        pairTitle: 'Pairing needed',
        pairHelp: 'Turn the TV on in TV mode (not art mode), tap Pair and accept the prompt on screen. To stop it asking again: Settings > General > Device Connection Manager > Access Notification > First Time Only.',
        pair: 'Pair', pairing: 'Waiting for the TV...', paired: 'Paired',
        refresh: 'Refresh status', syncNow: 'Sync now', syncQueued: 'Sync started',
        gallery: 'TV gallery', uploaded: 'Uploaded by the app', lastError: 'Last error',
        storageUsed: 'Space used',
        storageWarn: 'The app has uploaded {used} to {name}, more than {limit}. Delete the albums you do not use to free space on the TV.',
        enabled: 'Active', pause: 'Pause', resume: 'Resume',
        deleteTv: 'Delete TV', deleteTvMsg: 'Its time slots are deleted. Photos on the TV stay.',
        galleryHelp: 'Rotation only uses the photos of the active album. Photos from other albums stay on the TV until the album is deleted. Deleting album photos here also excludes them from the album.',
        galleryEmpty: 'There are no photos in "My Photos".', fromApp: 'App',
        deleteSelected: 'Delete selected ({n})', deletePhotos: 'Delete photos from TV',
        deletePhotosMsg: '{n} photos will be deleted from the TV.', photosDeleted: '{n} photos deleted',
        deletePagesMsg: 'It includes {n} layouts: all their photos will be excluded from the album so they are not generated again. The original files are not deleted.',
        loadingGallery: 'Reading the TV...',
        emptyScheduleTitle: 'No time slots', emptyScheduleText: 'Choose which album each TV shows, and when.',
        needTvAndAlbum: 'Add a TV and an album first.',
        newSlot: 'Add slot', editSlot: 'Time slot', tv: 'TV', album: 'Album', daysLabel: 'Days',
        start: 'From', end: 'To', slotEnabled: 'Active', slotPaused: 'Paused',
        scheduleHint: 'Outside the slots rotation stops and the TV stays in art mode.',
        everyDay: 'Every day', weekdays: 'Weekdays', weekends: 'Weekends',
        dayShort: ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'],
        deleteSlot: 'Delete slot', deleteSlotMsg: 'The TV will stop showing this album at that time.',
        theme: 'Theme', themeOpt: { system: 'System', light: 'Light', dark: 'Dark' },
        language: 'Language', version: 'Version {v}',
        aiTitle: 'Gemini', aiKey: 'API key', aiModel: 'Model', aiLimit: 'Maximum requests per day',
        aiKeySet: 'Set (ends in {hint})', aiKeyNone: 'Not set', aiUsage: '{n} requests today',
        aiKeyPlaceholder: 'Paste a key to change it', aiTest: 'Test', aiTestOk: 'Gemini is responding.',
        aiRemove: 'Remove key',
        settingsHelp: [
            ['Theme and language', 'Saved on this device only.'],
            ['Allowed folders', 'NAS folders that can be added to albums. Set in config.yaml (media.roots).'],
            ['Gemini', 'Only used by albums with Smart crop. The key is stored on the NAS and never shown again. The daily limit prevents unexpected costs.'],
        ],
        err: {
            network: 'Could not reach the server.',
            not_found: 'It no longer exists.',
            invalid_name: 'Enter a name.',
            invalid_host: 'Enter a valid IP address.',
            tv_unreachable: 'No TV found at that address. Make sure it is on.',
            not_a_frame_tv: 'That TV is not a The Frame.',
            pair_failed: 'Pairing failed. Put the TV in TV mode and accept the prompt.',
            tv_not_paired: 'Pair the TV first.',
            tv_unavailable: 'The TV is not responding. It must be in art mode.',
            tv_busy: 'The TV is busy with another task. Try again shortly.',
            tv_timeout: 'The TV took too long to respond.',
            thumbnail_failed: 'Could not read the thumbnail.',
            invalid_content_ids: 'Invalid selection.',
            invalid_path: 'That folder does not exist.',
            path_not_allowed: 'That folder is outside the allowed ones.',
            source_exists: 'That folder is already in the album.',
            invalid_matte: 'Invalid matte.',
            invalid_interval: 'Invalid interval.',
            invalid_days: 'Pick at least one day.',
            invalid_time: 'Invalid time.',
            invalid_time_range: 'Start and end time cannot be the same.',
            slot_overlap: 'It overlaps another slot of that TV.',
            invalid_icloud_url: 'Paste the public album link (photos.icloud.com/shared/album/... or icloud.com/sharedalbum/#...).',
            icloud_album_not_public: 'The album is not public or the link has expired. Allow "Anyone with the Link" or turn on "Public Website".',
            icloud_unreachable: 'Could not reach iCloud.',
            invalid_composition_mode: 'Invalid layout mode.',
            invalid_background: 'Invalid background.',
            invalid_single_fit: 'Invalid setting for single photos.',
            gemini_key_missing: 'The Gemini key is missing. Set it up in Settings.',
            gemini_key_invalid: 'Gemini rejected the key.',
            gemini_unreachable: 'Could not reach Gemini. It will retry; photos are center-cropped meanwhile.',
            gemini_response_invalid: 'Gemini returned an invalid response.',
            gemini_quota_exceeded: 'The Gemini request limit was reached. It will continue later.',
            invalid_gemini_model: 'That Gemini model does not exist.',
            invalid_gemini_limit: 'Enter a limit between 1 and 100000.',
            composition_source_unavailable: 'One of the layout photos is missing. Rescan the album.',
            composition_render_failed: 'The layout could not be generated: a photo is damaged or too large.',
            generic: 'Something went wrong. Please try again.',
        },
    },
};

const STORE_PREFIX = 'fa_';
const THEME_COLORS = { dark: '#0b0f19', light: '#eef1f6' };

const S = {
    lang: readStorage('lang') || (navigator.language || 'en').slice(0, 2),
    tab: 'albums',
    version: '',
    meta: { mattes: ['none'], intervals: [60], roots: [], max_images: 100, storage_warn_mb: 1024 },
    albums: [],
    tvs: [],
    slots: [],
};

// State of the open sheet's form (selected chips, gallery selection...)
let F = {};

/* ------------------------------------------------------------- helpers */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function readStorage(key) {
    try { return localStorage.getItem(STORE_PREFIX + key); } catch (e) { return null; }
}

function writeStorage(key, value) {
    try { localStorage.setItem(STORE_PREFIX + key, value); } catch (e) { /* private mode */ }
}

function t(key, vars) {
    const dict = I18N[S.lang] || I18N.en;
    let value = key.split('.').reduce((o, k) => (o == null ? undefined : o[k]), dict);
    if (value === undefined) value = key;
    if (vars && typeof value === 'string') {
        value = value.replace(/\{(\w+)\}/g, (_, k) => (vars[k] ?? ''));
    }
    return value;
}

function esc(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

async function api(path, { method = 'GET', body } = {}) {
    let res;
    try {
        res = await fetch(path, {
            method,
            headers: body ? { 'Content-Type': 'application/json' } : undefined,
            body: body ? JSON.stringify(body) : undefined,
        });
    } catch (e) {
        throw new Error('network');
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'generic');
    return data;
}

function errText(e) {
    return (I18N[S.lang] || I18N.en).err[e && e.message] || t('err.generic');
}

function toast(message, kind = 'ok') {
    const el = document.createElement('div');
    el.className = `toast ${kind}`;
    el.textContent = message;
    $('#toasts').appendChild(el);
    setTimeout(() => el.classList.add('hide'), 3200);
    setTimeout(() => el.remove(), 3600);
}

function fmtDateTime(iso) {
    return iso ? new Date(iso).toLocaleString(t('locale'), { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '–';
}

function intervalLabel(m) {
    if (m < 60) return t('minutes', { n: m });
    if (m < 1440) return t('hours', { n: m / 60 });
    return m === 1440 ? t('oneDay') : t('days', { n: m / 1440 });
}

function fmtMB(bytes) {
    const mb = bytes / 1048576;
    return t('megabytes', { n: mb.toLocaleString(t('locale'), { maximumFractionDigits: mb < 10 ? 1 : 0 }) });
}

function storageWarning(tv) {
    const limit = (S.meta.storage_warn_mb || 1024) * 1048576;
    if (!tv.uploaded_bytes || tv.uploaded_bytes <= limit) return '';
    return `<div class="banner warn"><p>${esc(t('storageWarn', { name: tv.name, used: fmtMB(tv.uploaded_bytes), limit: fmtMB(limit) }))}</p></div>`;
}

function matteLabel(id) {
    if (id === 'none') return t('matteStyle.none');
    const [style, color] = id.split('_');
    return `${t(`matteStyle.${style}`)} · ${t(`matteColor.${color}`)}`;
}

function daysLabel(mask) {
    if (mask === 127) return t('everyDay');
    if (mask === 31) return t('weekdays');
    if (mask === 96) return t('weekends');
    return t('dayShort').filter((_, i) => mask & (1 << i)).join(' ');
}

function stateTag(tv) {
    if (!tv.enabled) return `<span class="tag">${t('disabled')}</span>`;
    const state = tv.paired ? (tv.state || 'unknown') : 'on';
    const kind = { art: 'ok', tv: 'warn', on: 'warn', offline: 'danger' }[state] || '';
    return `<span class="tag ${kind}">${esc(t(`states.${state}`))}</span>`;
}

function chip(name, value, label, on, disabled = false) {
    return `<button type="button" class="chip${on ? ' on' : ''}" data-chip="${name}" data-value="${esc(value)}"${disabled ? ' disabled' : ''}>${esc(label)}</button>`;
}

function chips(name, options, selected) {
    return `<div class="chips">${options.map(([value, label]) => chip(name, value, label, selected(value))).join('')}</div>`;
}

function busy(btn, on) {
    if (!btn) return;
    btn.disabled = on;
    if (on) {
        btn.dataset.label = btn.innerHTML;
        btn.innerHTML = `<span class="spinner inline"></span>${btn.dataset.label}`;
    } else if (btn.dataset.label) {
        btn.innerHTML = btn.dataset.label;
    }
}

const CHEVRON = '<svg class="chev" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>';
const FOLDER = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>';
const CLOUD = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17.5 19H7a5 5 0 1 1 .9-9.9A6 6 0 0 1 19.4 11 4 4 0 0 1 17.5 19z"/></svg>';

/* --------------------------------------------------------------- sheet */

// helpKey: I18N list of [term, explanation] shown by the sheet's help button
function openSheet(title, html, onMount, helpKey) {
    const panel = $('.sheet-panel');
    panel.style.transform = '';
    panel.classList.remove('settle', 'dragging');
    $('#sheetTitle').textContent = title;
    $('#sheetBody').innerHTML = html;
    const helpBtn = $('#sheetHelp');
    helpBtn.hidden = !helpKey;
    helpBtn.dataset.help = helpKey || '';
    helpBtn.setAttribute('aria-expanded', 'false');
    $('#sheet').hidden = false;
    document.body.classList.add('no-scroll');
    if (onMount) onMount($('#sheetBody'));
}

function toggleHelp(btn) {
    const open = $('#sheetHelpPanel');
    btn.setAttribute('aria-expanded', String(!open));
    if (open) { open.remove(); return; }
    const vars = { max: S.meta.max_images };
    $('#sheetBody').insertAdjacentHTML('afterbegin', `
        <dl class="banner help" id="sheetHelpPanel">${t(btn.dataset.help).map(([term, text]) =>
            `<dt>${esc(term)}</dt><dd>${esc(text.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? ''))}</dd>`).join('')}</dl>`);
    $('.sheet-panel').scrollTo({ top: 0, behavior: 'smooth' });
}

function closeSheet() {
    $('#sheet').hidden = true;
    $('#sheetBody').innerHTML = '';
    document.body.classList.remove('no-scroll');
    F = {};
}

function confirmSheet(title, message, okLabel, onOk) {
    openSheet(title, `
        <p class="muted">${esc(message)}</p>
        <div class="actions">
            <button type="button" class="btn ghost" data-close>${t('cancel')}</button>
            <button type="button" class="btn danger" id="confirmOk">${esc(okLabel)}</button>
        </div>`, body => {
        $('#confirmOk', body).onclick = async e => {
            e.target.disabled = true;
            await onOk();
        };
    });
}

/* -------------------------------------------------------------- loading */

async function loadAll() {
    const [health, meta, albums, tvs, slots] = await Promise.allSettled([
        api('/api/health'), api('/api/meta'), api('/api/albums'), api('/api/tvs'), api('/api/schedule'),
    ]);
    if (health.status === 'fulfilled') S.version = health.value.version;
    if (meta.status === 'fulfilled') S.meta = meta.value;
    if (albums.status === 'fulfilled') S.albums = albums.value;
    if (tvs.status === 'fulfilled') S.tvs = tvs.value;
    if (slots.status === 'fulfilled') S.slots = slots.value;
    const failed = [albums, tvs, slots].find(r => r.status === 'rejected');
    if (failed) toast(errText(failed.reason), 'error');
    render();
}

async function reload(...what) {
    const urls = { albums: '/api/albums', tvs: '/api/tvs', slots: '/api/schedule' };
    const values = await Promise.all(what.map(k => api(urls[k])));
    what.forEach((k, i) => { S[k] = values[i]; });
    render();
}

function setLang(lang, rerender = true) {
    S.lang = I18N[lang] ? lang : 'en';
    document.documentElement.lang = S.lang;
    writeStorage('lang', S.lang);
    if (rerender) render();
}

/* ------------------------------------------------------------- rendering */

const TABS = {
    albums: { title: 'tabAlbums', view: renderAlbums },
    tvs: { title: 'tabTvs', view: renderTvs },
    schedule: { title: 'tabSchedule', view: renderSchedule },
};

function render() {
    const tab = TABS[S.tab] || TABS.albums;
    const title = t(tab.title);
    $('#smallTitle').textContent = title;
    $('#settingsBtn').setAttribute('aria-label', t('settings'));
    $('#sheetHelp').setAttribute('aria-label', t('help'));
    $('#sheetClose').setAttribute('aria-label', t('close'));
    $$('#tabs .tab').forEach(b => {
        $('.tab-label', b).textContent = t(TABS[b.dataset.tab].title);
        b.setAttribute('aria-selected', String(b.dataset.tab === S.tab));
    });
    $('#view').innerHTML = `<h1 class="large-title">${esc(title)}</h1>${tab.view()}`;
}

function renderEmpty(titleKey, textKey, action, labelKey) {
    return `
        <section class="empty">
            <img src="/static/icon-192.png" alt="" width="72" height="72">
            <h1>${t(titleKey)}</h1>
            <p class="muted">${t(textKey)}</p>
            ${action ? `<button type="button" class="btn primary big" data-action="${action}">${t(labelKey)}</button>` : ''}
        </section>`;
}

function topAction(action, labelKey) {
    return `<div class="actions top"><button type="button" class="btn primary small" data-action="${action}">${t(labelKey)}</button></div>`;
}

function renderAlbums() {
    if (!S.albums.length) return renderEmpty('emptyAlbumsTitle', 'emptyAlbumsText', 'new-album', 'newAlbum');
    return `${topAction('new-album', 'newAlbum')}
        <section class="card"><div class="rows">${S.albums.map(a => `
            <button type="button" class="row" data-album="${a.id}">
                <span class="row-main">
                    <span class="row-title">${esc(a.name)}</span>
                    <span class="row-meta">
                        ${a.sources.length ? esc(albumCount(a)) : `<span class="tag warn">${t('noSources')}</span>`}
                        · ${esc(intervalLabel(a.interval))} · ${t(a.shuffle ? 'shuffle' : 'sequential')}
                        ${a.tv_bytes ? `· ${esc(t('onTv', { size: fmtMB(a.tv_bytes) }))}` : ''}
                    </span>
                </span>
                ${CHEVRON}
            </button>`).join('')}</div></section>`;
}

function albumCount(a) {
    return a.composition_mode === 'auto'
        ? t('outputMeta', { photos: a.output.photos, total: a.output.total })
        : t('albumMeta', { n: a.included, total: a.images });
}

function renderTvs() {
    if (!S.tvs.length) return renderEmpty('emptyTvsTitle', 'emptyTvsText', 'new-tv', 'newTv');
    return `${topAction('new-tv', 'newTv')}
        ${S.tvs.map(storageWarning).join('')}
        <section class="card"><div class="rows">${S.tvs.map(tv => `
            <button type="button" class="row" data-tv="${tv.id}">
                <span class="row-main">
                    <span class="row-title">${esc(tv.name)}</span>
                    <span class="row-meta">
                        ${stateTag(tv)}
                        ${esc(tv.active_album ? t('nowShowing', { name: tv.active_album.name }) : t('noActiveSlot'))}
                        ${tv.uploaded_bytes ? `· ${esc(fmtMB(tv.uploaded_bytes))}` : ''}
                        ${tv.last_error ? `<span class="tag danger">${esc(errText(new Error(tv.last_error)))}</span>` : ''}
                    </span>
                </span>
                ${CHEVRON}
            </button>`).join('')}</div></section>`;
}

function renderSchedule() {
    if (!S.tvs.length || !S.albums.length) {
        return `<div class="banner warn"><p>${t('needTvAndAlbum')}</p></div>`;
    }
    const albumName = id => (S.albums.find(a => a.id === id) || {}).name || '–';
    return `<p class="hint" style="margin: 0 4px 14px">${t('scheduleHint')}</p>
        <div class="grid">${S.tvs.map(tv => {
            const slots = S.slots.filter(s => s.tv_id === tv.id);
            return `
            <section class="card">
                <div class="card-head">
                    <h2>${esc(tv.name)}</h2>
                    <button type="button" class="btn small ghost" data-action="new-slot" data-tv-id="${tv.id}">${t('newSlot')}</button>
                </div>
                ${slots.length ? `<div class="rows">${slots.map(s => `
                    <button type="button" class="row" data-slot="${s.id}">
                        <span class="row-main">
                            <span class="row-title">${esc(s.start)} – ${esc(s.end)} · ${esc(albumName(s.album_id))}</span>
                            <span class="row-meta">${esc(daysLabel(s.days))}${s.enabled ? '' : ` <span class="tag">${t('slotPaused')}</span>`}</span>
                        </span>
                        ${CHEVRON}
                    </button>`).join('')}</div>` : `<p class="muted small">${t('emptyScheduleText')}</p>`}
            </section>`;
        }).join('')}</div>`;
}

/* --------------------------------------------------------------- albums */

// Grouped as rotation (when) then display (how each image looks); explanations live in the help panel
function albumFormHtml(a) {
    const interval = S.meta.intervals.includes(F.interval) ? F.interval : S.meta.intervals[0];
    return `
        <label class="field"><span>${t('name')}</span>
            <input name="name" maxlength="60" autocomplete="off" value="${esc(a.name || '')}" required></label>
        <h3 class="form-group">${t('rotation')}</h3>
        <div class="field-row">
            <label class="field"><span>${t('interval')}</span>
                <select name="interval">${S.meta.intervals.map(m =>
                    `<option value="${m}"${m === interval ? ' selected' : ''}>${esc(intervalLabel(m))}</option>`).join('')}</select></label>
            <div class="field"><span>${t('order')}</span>
                ${chips('shuffle', [['1', t('shuffle')], ['0', t('sequential')]], v => (v === '1') === F.shuffle)}</div>
        </div>
        <h3 class="form-group">${t('display')}</h3>
        <div class="field"><span>${t('singleFit')}</span>
            ${chips('singleFit', [['crop', t('fitCrop')], ['fit', t('fitWhole')]], v => v === F.singleFit)}</div>
        <div class="field"><div class="chips">
            ${chip('composition', '1', t('composition'), F.composition)}
            ${chip('dateStamp', '1', t('dateStamp'), F.dateStamp)}
            ${chip('subject', '1', t('subjectDetection'), F.subject, !S.meta.ai && !F.subject)}</div>
            ${S.meta.ai ? '' : `<p class="hint">${t('subjectNeedsKey')}</p>`}</div>
        <div class="field" id="backgroundField"${showBackground() ? '' : ' hidden'}><span>${t('background')}</span>
            ${chips('background', [['paper', t('bgPaper')], ['blur', t('bgBlur')]], v => v === F.background)}</div>
        <label class="field"><span>${t('matte')}</span>
            <select name="matte">${S.meta.mattes.map(m =>
                `<option value="${esc(m)}"${m === (a.matte || 'none') ? ' selected' : ''}>${esc(matteLabel(m))}</option>`).join('')}</select></label>`;
}

// The background only fills space left by layouts or by photos shown whole
function showBackground() {
    return F.composition || F.singleFit === 'fit';
}

function openNewAlbum() {
    F = { interval: S.meta.intervals.includes(60) ? 60 : S.meta.intervals[0], shuffle: true, composition: false,
          dateStamp: true, singleFit: 'crop', background: 'paper', subject: false };
    openSheet(t('newAlbum'), `
        <form class="stack" id="albumForm" novalidate>
            ${albumFormHtml({})}
            <div class="actions">
                <button type="button" class="btn ghost" data-close>${t('cancel')}</button>
                <button type="submit" class="btn primary">${t('save')}</button>
            </div>
        </form>`, body => {
        const form = $('#albumForm', body);
        form.onsubmit = async e => {
            e.preventDefault();
            const btn = $('button[type="submit"]', form);
            busy(btn, true);
            try {
                const album = await api('/api/albums', { method: 'POST', body: albumBody(form) });
                await reload('albums');
                openAlbum(album.id);
            } catch (err) {
                toast(errText(err), 'error');
                busy(btn, false);
            }
        };
    }, 'albumHelp');
}

function albumBody(form) {
    return {
        name: form.elements.name.value.trim(), matte: form.elements.matte.value,
        interval: Number(form.elements.interval.value), shuffle: F.shuffle, composition_mode: F.composition ? 'auto' : 'off',
        date_stamp: F.dateStamp, single_fit: F.singleFit, background: F.background, subject_detection: F.subject,
    };
}

function openAlbum(id) {
    const a = S.albums.find(x => x.id === id);
    if (!a) return;
    F = { albumId: a.id, interval: a.interval, shuffle: a.shuffle, composition: a.composition_mode === 'auto',
          dateStamp: a.date_stamp, singleFit: a.single_fit, background: a.background,
          subject: a.subject_detection };
    const auto = a.composition_mode === 'auto';
    openSheet(a.name, `
        <form class="stack" id="albumForm" novalidate>
            ${a.subject_detection && a.subject_error
                ? `<div class="banner warn"><p>${esc(errText(new Error(a.subject_error)))}</p></div>` : ''}
            ${albumFormHtml(a)}
            <div class="actions"><button type="submit" class="btn primary small">${t('save')}</button></div>
        </form>
        <section class="set">
            <div class="set-row"><h3>${t('sources')}</h3>
                <span class="chips">
                    <button type="button" class="btn small ghost" data-action="add-folder">${t('addFolder')}</button>
                    <button type="button" class="btn small ghost" data-action="add-icloud">${t('addIcloud')}</button>
                </span></div>
            ${a.sources.length ? `<div class="rows">${a.sources.map(s => `
                <div class="row">
                    ${s.kind === 'icloud' ? CLOUD : FOLDER}
                    <span class="row-main">
                        <span class="row-title path">${esc(s.kind === 'icloud' ? (s.label || t('icloudTitle')) : s.path)}</span>
                        <span class="row-meta">${s.recursive ? esc(t('subfolders')) : ''}
                            ${s.kind === 'icloud' && !s.last_scan ? `<span class="tag">${t('downloading')}</span>` : ''}
                            ${s.last_error ? `<span class="tag danger">${esc(errText(new Error(s.last_error)))}</span>` : ''}</span>
                    </span>
                    <button type="button" class="btn small ghost danger-text" data-action="del-source" data-id="${s.id}">${t('delete')}</button>
                </div>`).join('')}</div>` : `<p class="muted small">${t('noSources')}</p>`}
        </section>
        ${auto ? `<section class="set">
            <div class="set-row"><h3>${t('compositions')} <span class="muted" id="albumOutput">${esc(albumCount(a))}</span></h3>
                <button type="button" class="btn small ghost" data-action="compose">${t('regenerate')}</button></div>
            <div id="albumPages" class="thumbs"><div class="small-loading"><span class="spinner"></span></div></div>
        </section>` : ''}
        <section class="set">
            <div class="set-row"><h3>${t(auto ? 'originals' : 'images')} <span class="muted">${esc(t('albumMeta', { n: a.included, total: a.images }))}</span></h3>
                <button type="button" class="btn small ghost" data-action="rescan">${t('rescan')}</button></div>
            <div id="albumImages" class="thumbs"><div class="small-loading"><span class="spinner"></span></div></div>
        </section>
        <div class="actions spread">
            <button type="button" class="btn ghost danger-text" data-action="del-album">${t('delete')}</button>
            <button type="button" class="btn primary" data-close>${t('close')}</button>
        </div>`, body => {
        const form = $('#albumForm', body);
        form.onsubmit = async e => {
            e.preventDefault();
            const btn = $('button[type="submit"]', form);
            busy(btn, true);
            try {
                const saved = await api(`/api/albums/${a.id}`, { method: 'PATCH', body: albumBody(form) });
                toast(t('saved'));
                await reload('albums');
                if (saved.composition_mode !== a.composition_mode) { openAlbum(a.id); return; }
                $('#sheetTitle').textContent = form.elements.name.value.trim();
            } catch (err) {
                toast(errText(err), 'error');
            }
            busy(btn, false);
        };
        loadAlbumImages(a.id);
        if (auto) loadAlbumPages(a.id);
    }, 'albumHelp');
}

function pageThumb(p) {
    const status = p.status === 'pending' && p.rendered_revision ? 'updating' : p.status;
    const tag = p.status === 'error'
        ? `<span class="tag danger">${esc(errText(new Error(p.last_error)))}</span>`
        : (p.status !== 'ready' ? `<span class="tag">${esc(t(`pageStatus.${status}`))}</span>` : '');
    return `<button type="button" class="thumb" data-page="${p.id}" title="${esc(p.members.map(m => m.key).join(', '))}">
        ${p.rendered_revision ? `<img src="/api/pages/${p.id}/thumb?rev=${p.rendered_revision}&v=${esc(p.v)}" alt="" loading="lazy">`
        : '<span class="small-loading" style="min-height:100%"><span class="spinner"></span></span>'}${tag}</button>`;
}

// Layouts are rendered in the background: poll their status without blocking the UI
async function loadAlbumPages(albumId) {
    clearTimeout(F.pagesTimer);
    let pages, albums;
    try {
        [pages, albums] = await Promise.all([api(`/api/albums/${albumId}/pages`), api('/api/albums')]);
    } catch (err) {
        toast(errText(err), 'error');
        return;
    }
    S.albums = albums;
    const box = $('#albumPages');
    const a = S.albums.find(x => x.id === albumId);
    if (!box || !a || F.albumId !== albumId) return;
    F.pages = pages;
    $('#albumOutput').textContent = albumCount(a);
    const waiting = !a.output.current || a.output.pending > 0;
    const status = !a.output.current ? t('composeWaiting')
        : (a.output.pending ? t('composePending', { n: a.output.pending }) : '');
    box.innerHTML = (status ? `<p class="hint"><span class="spinner inline"></span>${esc(status)}</p>` : '')
        + (pages.length ? pages.map(pageThumb).join('') : (waiting ? '' : `<p class="muted small">${t('noCompositions')}</p>`));
    if (waiting) F.pagesTimer = setTimeout(() => loadAlbumPages(albumId), 4000);
}

async function composeAlbum(btn) {
    busy(btn, true);
    try {
        await api(`/api/albums/${F.albumId}/compose`, { method: 'POST' });
        toast(t('regenerating'));
        loadAlbumPages(F.albumId);
    } catch (err) {
        toast(errText(err), 'error');
    }
    busy(btn, false);
}

function openPage(pageId) {
    const p = (F.pages || []).find(x => x.id === pageId);
    if (!p) return;
    openSheet(t('page'), `
        ${p.rendered_revision ? `<div class="thumb large"><img src="/api/pages/${p.id}/image?rev=${p.rendered_revision}&v=${esc(p.v)}" alt=""></div>
            <p class="hint"><a href="/api/pages/${p.id}/image?rev=${p.rendered_revision}&v=${esc(p.v)}" target="_blank" rel="noopener">${t('openFull')}</a></p>`
        : '<div class="small-loading"><span class="spinner"></span></div>'}
        ${p.status === 'error' ? `<div class="banner warn"><p>${esc(errText(new Error(p.last_error)))}</p></div>` : ''}
        <section class="set">
            <h3>${t('pageMembers')}</h3>
            <div class="thumbs">${p.members.map(m => `
                <div class="thumb" title="${esc(m.key)}"><img src="/api/images/${m.id}/thumb?v=${esc(m.v)}" alt="" loading="lazy">
                    <span class="tag">${esc(m.key)}</span></div>`).join('')}</div>
        </section>
        <div class="actions">
            <button type="button" class="btn primary" data-action="back-album">${t('back')}</button>
        </div>`);
}

async function loadAlbumImages(albumId) {
    let images;
    try {
        images = await api(`/api/albums/${albumId}/images`);
    } catch (err) {
        toast(errText(err), 'error');
        return;
    }
    const box = $('#albumImages');
    if (!box || F.albumId !== albumId) return;
    box.innerHTML = images.length ? images.map(img => `
        <button type="button" class="thumb${img.excluded ? ' off' : ''}" data-image="${img.id}" title="${esc(img.key)}">
            <img src="/api/images/${img.id}/thumb?v=${esc(img.v)}" alt="" loading="lazy">
        </button>`).join('') : `<p class="muted small">${t('noImages')}</p>`;
}

async function toggleImage(btn) {
    const excluded = !btn.classList.contains('off');
    btn.classList.toggle('off', excluded);
    try {
        await api(`/api/images/${btn.dataset.image}`, { method: 'PATCH', body: { excluded } });
        await reload('albums');
    } catch (err) {
        btn.classList.toggle('off', !excluded);
        toast(errText(err), 'error');
    }
}

async function rescanAlbum(btn) {
    busy(btn, true);
    try {
        await api(`/api/albums/${F.albumId}/rescan`, { method: 'POST' });
        await reload('albums');
        toast(t('rescanned'));
        openAlbum(F.albumId);
    } catch (err) {
        toast(errText(err), 'error');
        busy(btn, false);
    }
}

function deleteAlbum() {
    const id = F.albumId;
    confirmSheet(t('deleteAlbum'), t('deleteAlbumMsg'), t('delete'), async () => {
        try {
            await api(`/api/albums/${id}`, { method: 'DELETE' });
            toast(t('deleted'));
            await reload('albums', 'slots');
        } catch (err) {
            toast(errText(err), 'error');
        }
        closeSheet();
    });
}

function deleteSource(sourceId) {
    const albumId = F.albumId;
    confirmSheet(t('deleteSource'), t('deleteSourceMsg'), t('delete'), async () => {
        try {
            await api(`/api/albums/${albumId}/sources/${sourceId}`, { method: 'DELETE' });
            await reload('albums');
        } catch (err) {
            toast(errText(err), 'error');
        }
        openAlbum(albumId);
    });
}

/* ------------------------------------------------------- folder browser */

async function openBrowser(albumId, path = '') {
    let data;
    try {
        data = await api(`/api/browse?path=${encodeURIComponent(path)}`);
    } catch (err) {
        toast(errText(err), 'error');
        return;
    }
    const recursive = F.recursive || false;
    F = { albumId, path: data.path, recursive };
    const rows = [];
    if (data.path) {
        rows.push(`<button type="button" class="row" data-browse="${esc(data.parent || '')}">
            <span class="row-main"><span class="row-title">${t('up')}</span></span></button>`);
    }
    data.dirs.forEach(d => rows.push(`
        <button type="button" class="row" data-browse="${esc(d.path)}">
            ${FOLDER}<span class="row-main"><span class="row-title">${esc(d.name)}</span></span>${CHEVRON}
        </button>`));
    openSheet(t('chooseFolder'), `
        ${data.path ? `<p class="eyebrow path">${esc(data.path)}</p>
            <p class="hint">${esc(t('folderImages', { n: data.images }))}</p>` : `<p class="hint">${t('roots')}</p>`}
        <div class="rows" style="margin-top:10px">${rows.join('')}</div>
        ${data.path ? `<div class="field">${chips('recursive', [['1', t('includeSubfolders')]], () => F.recursive)}</div>` : ''}
        <div class="actions">
            <button type="button" class="btn ghost" data-action="back-album">${t('back')}</button>
            <button type="button" class="btn primary" data-action="use-folder"${data.path ? '' : ' disabled'}>${t('useFolder')}</button>
        </div>`);
}

async function useFolder(btn) {
    busy(btn, true);
    try {
        await api(`/api/albums/${F.albumId}/sources`, { method: 'POST', body: { path: F.path, recursive: F.recursive } });
        toast(t('folderAdded'));
        await reload('albums');
        openAlbum(F.albumId);
    } catch (err) {
        toast(errText(err), 'error');
        busy(btn, false);
    }
}

/* ------------------------------------------------------------- icloud */

function openIcloudForm() {
    const albumId = F.albumId;
    openSheet(t('icloudTitle'), `
        <form class="stack" id="icloudForm" novalidate>
            <p class="hint">${t('icloudHelp')}</p>
            <label class="field"><span>${t('icloudUrl')}</span>
                <input name="url" type="url" autocomplete="off" placeholder="https://photos.icloud.com/shared/album/..." required></label>
            <div class="actions">
                <button type="button" class="btn ghost" data-action="back-album">${t('back')}</button>
                <button type="submit" class="btn primary">${t('save')}</button>
            </div>
        </form>`, body => {
        const form = $('#icloudForm', body);
        form.onsubmit = async e => {
            e.preventDefault();
            const btn = $('button[type="submit"]', form);
            busy(btn, true);
            try {
                await api(`/api/albums/${albumId}/sources`, { method: 'POST', body: { kind: 'icloud', path: form.elements.url.value.trim() } });
                toast(t('icloudAdded'));
                await reload('albums');
                openAlbum(albumId);
            } catch (err) {
                toast(errText(err), 'error');
                busy(btn, false);
            }
        };
    });
}

/* ------------------------------------------------------------------ tvs */

function tvFormHtml(tv) {
    return `
        <label class="field"><span>${t('name')}</span>
            <input name="name" maxlength="60" autocomplete="off" value="${esc(tv.name || '')}" required></label>
        <label class="field"><span>${t('host')}</span>
            <input name="host" maxlength="253" autocomplete="off" inputmode="decimal" placeholder="192.168.1.50" value="${esc(tv.host || '')}" required></label>`;
}

function openTvForm(tv) {
    openSheet(tv ? tv.name : t('newTv'), `
        <form class="stack" id="tvForm" novalidate>
            ${tvFormHtml(tv || { name: 'The Frame' })}
            <div class="actions">
                <button type="button" class="btn ghost" ${tv ? `data-action="back-tv"` : 'data-close'}>${t('cancel')}</button>
                <button type="submit" class="btn primary">${t('save')}</button>
            </div>
        </form>`, body => {
        const form = $('#tvForm', body);
        form.onsubmit = async e => {
            e.preventDefault();
            const btn = $('button[type="submit"]', form);
            busy(btn, true);
            const payload = { name: form.elements.name.value.trim(), host: form.elements.host.value.trim() };
            try {
                const saved = tv
                    ? await api(`/api/tvs/${tv.id}`, { method: 'PATCH', body: payload })
                    : await api('/api/tvs', { method: 'POST', body: payload });
                toast(t(tv ? 'saved' : 'tvAdded'));
                await reload('tvs');
                openTv(saved.id);
            } catch (err) {
                toast(errText(err), 'error');
                busy(btn, false);
            }
        };
    });
}

function openTv(id) {
    const tv = S.tvs.find(x => x.id === id);
    if (!tv) return;
    F = { tvId: tv.id };
    openSheet(tv.name, `
        ${tv.paired ? '' : `<div class="banner warn"><p><b>${t('pairTitle')}.</b> ${t('pairHelp')}</p>
            <button type="button" class="btn small primary" data-action="pair">${t('pair')}</button></div>`}
        ${storageWarning(tv)}
        <div class="stats">
            <div class="stat"><span>${t('state')}</span><b>${stateTag(tv)}</b><small>${esc(fmtDateTime(tv.last_seen))}</small></div>
            <div class="stat"><span>${t('album')}</span><b class="small">${esc(tv.active_album ? tv.active_album.name : t('noActiveSlot'))}</b></div>
            <div class="stat"><span>${t('uploaded')}</span><b>${tv.uploaded}</b></div>
            <div class="stat"><span>${t('storageUsed')}</span><b>${esc(fmtMB(tv.uploaded_bytes || 0))}</b></div>
        </div>
        <section class="set">
            <div class="set-row"><span class="muted small">${t('model')}</span><span class="small">${esc(tv.model || '–')}</span></div>
            <div class="set-row"><span class="muted small">${t('host')}</span><span class="small">${esc(tv.host)}</span></div>
            <div class="set-row"><span class="muted small">${t('mac')}</span><span class="small">${esc(tv.mac || '–')}</span></div>
            ${tv.last_error ? `<div class="set-row"><span class="muted small">${t('lastError')}</span><span class="tag danger">${esc(errText(new Error(tv.last_error)))}</span></div>` : ''}
        </section>
        <div class="actions" style="justify-content:flex-start">
            <button type="button" class="btn small ghost" data-action="tv-refresh">${t('refresh')}</button>
            ${tv.paired ? `<button type="button" class="btn small ghost" data-action="tv-sync">${t('syncNow')}</button>
            <button type="button" class="btn small ghost" data-action="tv-gallery">${t('gallery')}</button>` : ''}
            <button type="button" class="btn small ghost" data-action="tv-edit">${t('edit')}</button>
            <button type="button" class="btn small ghost" data-action="tv-toggle">${t(tv.enabled ? 'pause' : 'resume')}</button>
            ${tv.paired ? `<button type="button" class="btn small ghost" data-action="pair">${t('pair')}</button>` : ''}
        </div>
        <div class="actions spread">
            <button type="button" class="btn ghost danger-text" data-action="del-tv">${t('delete')}</button>
            <button type="button" class="btn primary" data-close>${t('close')}</button>
        </div>`);
}

async function tvCall(btn, path, method, okKey) {
    const id = F.tvId;
    busy(btn, true);
    try {
        await api(`/api/tvs/${id}${path}`, { method });
        if (okKey) toast(t(okKey));
        await reload('tvs');
        openTv(id);
    } catch (err) {
        toast(errText(err), 'error');
        busy(btn, false);
    }
}

async function toggleTv(btn) {
    const tv = S.tvs.find(x => x.id === F.tvId);
    busy(btn, true);
    try {
        await api(`/api/tvs/${tv.id}`, { method: 'PATCH', body: { enabled: !tv.enabled } });
        await reload('tvs');
        openTv(tv.id);
    } catch (err) {
        toast(errText(err), 'error');
        busy(btn, false);
    }
}

function deleteTv() {
    const id = F.tvId;
    confirmSheet(t('deleteTv'), t('deleteTvMsg'), t('delete'), async () => {
        try {
            await api(`/api/tvs/${id}`, { method: 'DELETE' });
            toast(t('deleted'));
            await reload('tvs', 'slots');
        } catch (err) {
            toast(errText(err), 'error');
        }
        closeSheet();
    });
}

/* -------------------------------------------------------------- gallery */

async function openGallery(tvId) {
    const tv = S.tvs.find(x => x.id === tvId);
    F = { tvId, selected: new Set(), pages: new Set() };
    openSheet(t('gallery'), `<div class="small-loading"><span class="spinner"></span><p class="hint">${t('loadingGallery')}</p></div>`);
    let items;
    try {
        items = await api(`/api/tvs/${tvId}/gallery`);
    } catch (err) {
        toast(errText(err), 'error');
        openTv(tvId);
        return;
    }
    if (F.tvId !== tvId) return;
    openSheet(`${t('gallery')} · ${tv.name}`, `
        <p class="hint">${t('galleryHelp')}</p>
        ${items.length ? `<div class="thumbs" style="margin-top:12px">${items.map(it => `
            <button type="button" class="thumb" data-gsel="${esc(it.content_id)}"${it.page_id ? ' data-gpage="1"' : ''} title="${esc(it.name || it.content_id)}">
                <img src="${it.image_id ? `/api/images/${it.image_id}/thumb?v=${esc(it.image_v)}` : `/api/tvs/${tvId}/gallery/${encodeURIComponent(it.content_id)}/thumb`}" alt="" loading="lazy">
                ${it.managed ? `<span class="tag ok">${esc([it.album || t('fromApp'), it.page_id ? t('page') : ''].filter(Boolean).join(' · '))}</span>` : ''}
            </button>`).join('')}</div>` : `<p class="muted" style="margin-top:12px">${t('galleryEmpty')}</p>`}
        <div class="actions spread">
            <button type="button" class="btn ghost" data-action="back-tv">${t('back')}</button>
            <button type="button" class="btn danger" data-action="gallery-delete" disabled>${esc(t('deleteSelected', { n: 0 }))}</button>
        </div>`);
}

function toggleGallerySelection(btn) {
    const cid = btn.dataset.gsel;
    if (F.selected.has(cid)) F.selected.delete(cid); else F.selected.add(cid);
    if (btn.dataset.gpage) {
        if (F.selected.has(cid)) F.pages.add(cid); else F.pages.delete(cid);
    }
    btn.classList.toggle('sel', F.selected.has(cid));
    const del = $('[data-action="gallery-delete"]');
    del.disabled = !F.selected.size;
    del.textContent = t('deleteSelected', { n: F.selected.size });
}

function deleteGallerySelection() {
    const tvId = F.tvId;
    const ids = Array.from(F.selected);
    let message = t('deletePhotosMsg', { n: ids.length });
    if (F.pages.size) message += ` ${t('deletePagesMsg', { n: F.pages.size })}`;
    confirmSheet(t('deletePhotos'), message, t('delete'), async () => {
        try {
            const res = await api(`/api/tvs/${tvId}/gallery/delete`, { method: 'POST', body: { content_ids: ids } });
            toast(t('photosDeleted', { n: res.deleted.length }));
            await reload('tvs', 'albums');
        } catch (err) {
            toast(errText(err), 'error');
        }
        openGallery(tvId);
    });
}

/* ------------------------------------------------------------- schedule */

function openSlot(id, tvId) {
    const s = S.slots.find(x => x.id === id) || {
        tv_id: tvId, album_id: S.albums[0].id, days: 127, start: '08:00', end: '23:00', enabled: true,
    };
    F = { slotId: s.id || null, days: s.days, enabled: s.enabled };
    const dayOptions = t('dayShort').map((label, i) => [String(i), label]);
    openSheet(t('editSlot'), `
        <form class="stack" id="slotForm" novalidate>
            <label class="field"><span>${t('tv')}</span>
                <select name="tv">${S.tvs.map(tv => `<option value="${tv.id}"${tv.id === s.tv_id ? ' selected' : ''}>${esc(tv.name)}</option>`).join('')}</select></label>
            <label class="field"><span>${t('album')}</span>
                <select name="album">${S.albums.map(a => `<option value="${a.id}"${a.id === s.album_id ? ' selected' : ''}>${esc(a.name)}</option>`).join('')}</select></label>
            <div class="field"><span>${t('daysLabel')}</span>${chips('day', dayOptions, v => F.days & (1 << Number(v)))}</div>
            <div class="field-row">
                <label class="field"><span>${t('start')}</span><input type="time" name="start" value="${esc(s.start)}" required></label>
                <label class="field"><span>${t('end')}</span><input type="time" name="end" value="${esc(s.end)}" required></label>
            </div>
            <div class="field">${chips('enabled', [['1', t('slotEnabled')]], () => F.enabled)}</div>
            <div class="actions ${s.id ? 'spread' : ''}">
                ${s.id ? `<button type="button" class="btn ghost danger-text" data-action="del-slot">${t('delete')}</button>` : ''}
                <span class="actions" style="margin:0">
                    <button type="button" class="btn ghost" data-close>${t('cancel')}</button>
                    <button type="submit" class="btn primary">${t('save')}</button>
                </span>
            </div>
        </form>`, body => {
        const form = $('#slotForm', body);
        form.onsubmit = async e => {
            e.preventDefault();
            const btn = $('button[type="submit"]', form);
            busy(btn, true);
            const payload = {
                tv_id: Number(form.elements.tv.value), album_id: Number(form.elements.album.value),
                days: F.days, start: form.elements.start.value, end: form.elements.end.value, enabled: F.enabled,
            };
            try {
                if (F.slotId) await api(`/api/schedule/${F.slotId}`, { method: 'PATCH', body: payload });
                else await api('/api/schedule', { method: 'POST', body: payload });
                toast(t('saved'));
                closeSheet();
                await reload('slots', 'tvs');
            } catch (err) {
                toast(errText(err), 'error');
                busy(btn, false);
            }
        };
    });
}

function deleteSlot() {
    const id = F.slotId;
    confirmSheet(t('deleteSlot'), t('deleteSlotMsg'), t('delete'), async () => {
        try {
            await api(`/api/schedule/${id}`, { method: 'DELETE' });
            toast(t('deleted'));
            await reload('slots', 'tvs');
        } catch (err) {
            toast(errText(err), 'error');
        }
        closeSheet();
    });
}

/* -------------------------------------------------------------- settings */

function currentTheme() {
    const v = document.documentElement.getAttribute('data-theme');
    return v === 'light' || v === 'dark' ? v : 'system';
}

function setTheme(value) {
    if (value === 'light' || value === 'dark') document.documentElement.setAttribute('data-theme', value);
    else document.documentElement.removeAttribute('data-theme');
    writeStorage('theme', value);
    // Match the browser status bar color to the theme
    const dark = value === 'dark' || (value === 'system' && matchMedia('(prefers-color-scheme: dark)').matches);
    $$('meta[name="theme-color"]').forEach(m => m.setAttribute('content', dark ? THEME_COLORS.dark : THEME_COLORS.light));
}

function openSettings() {
    const theme = currentTheme();
    openSheet(t('settings'), `
        <section class="set">
            <h3>${t('theme')}</h3>
            <div class="chips">${['system', 'light', 'dark'].map(v =>
                `<button type="button" class="chip${v === theme ? ' on' : ''}" data-theme-opt="${v}">${t(`themeOpt.${v}`)}</button>`).join('')}</div>
        </section>
        <section class="set">
            <h3>${t('language')}</h3>
            <div class="chips">${Object.keys(I18N).map(l =>
                `<button type="button" class="chip${l === S.lang ? ' on' : ''}" data-lang-opt="${l}">${l.toUpperCase()}</button>`).join('')}</div>
        </section>
        <section class="set">
            <h3>${t('roots')}</h3>
            ${S.meta.roots.map(r => `<p class="small path">${esc(r)}</p>`).join('') || '<p class="small muted">–</p>'}
        </section>
        <section class="set" id="aiBox"><h3>${t('aiTitle')}</h3>
            <div class="small-loading"><span class="spinner"></span></div></section>
        <p class="hint">${esc(t('version', { v: S.version || '–' }))}</p>`, () => loadAiSettings(), 'settingsHelp');
}

async function loadAiSettings() {
    let ai;
    try {
        ai = await api('/api/settings/ai');
    } catch (err) {
        toast(errText(err), 'error');
        return;
    }
    S.meta.ai = ai.configured;
    const box = $('#aiBox');
    if (!box) return;
    box.innerHTML = `<h3>${t('aiTitle')}</h3>
        <form class="stack" id="aiForm" novalidate>
            <label class="field"><span>${t('aiKey')}
                <span class="muted">· ${esc(ai.configured ? t('aiKeySet', { hint: ai.key_hint }) : t('aiKeyNone'))}</span></span>
                <input name="api_key" type="password" autocomplete="off" spellcheck="false"
                    placeholder="${esc(t('aiKeyPlaceholder'))}"></label>
            <label class="field"><span>${t('aiModel')}</span>
                <input name="model" autocomplete="off" spellcheck="false" value="${esc(ai.model)}"></label>
            <label class="field"><span>${t('aiLimit')}
                <span class="muted">· ${esc(t('aiUsage', { n: ai.calls_today }))}</span></span>
                <input name="max_calls_per_day" type="number" min="1" max="100000" inputmode="numeric"
                    value="${esc(ai.max_calls_per_day)}"></label>
            <div class="actions">
                ${ai.configured ? `<button type="button" class="btn ghost danger-text" id="aiRemove">${t('aiRemove')}</button>` : ''}
                ${ai.configured ? `<button type="button" class="btn ghost" id="aiTest">${t('aiTest')}</button>` : ''}
                <button type="submit" class="btn primary">${t('save')}</button>
            </div>
        </form>`;
    const form = $('#aiForm', box);
    const save = async (payload, btn) => {
        busy(btn, true);
        try {
            await api('/api/settings/ai', { method: 'PUT', body: payload });
            toast(t('saved'));
            loadAiSettings();
        } catch (err) {
            toast(errText(err), 'error');
            busy(btn, false);
        }
    };
    form.onsubmit = e => {
        e.preventDefault();
        const payload = {
            model: form.elements.model.value.trim(),
            max_calls_per_day: Number(form.elements.max_calls_per_day.value),
        };
        const key = form.elements.api_key.value.trim();
        if (key) payload.api_key = key;
        save(payload, $('button[type="submit"]', form));
    };
    const remove = $('#aiRemove', form);
    if (remove) remove.onclick = () => save({ api_key: '' }, remove);
    const test = $('#aiTest', form);
    if (test) test.onclick = async () => {
        busy(test, true);
        try {
            await api('/api/settings/ai/test', { method: 'POST' });
            toast(t('aiTestOk'));
        } catch (err) {
            toast(errText(err), 'error');
        }
        busy(test, false);
    };
}

/* ---------------------------------------------------------------- events */

function onChip(chip) {
    const { chip: name, value } = chip.dataset;
    const group = chip.parentElement;
    if (name === 'shuffle') F.shuffle = value === '1';
    else if (name === 'day') F.days ^= 1 << Number(value);
    else if (name === 'enabled') F.enabled = !F.enabled;
    else if (name === 'recursive') F.recursive = !F.recursive;
    else if (name === 'composition') F.composition = !F.composition;
    else if (name === 'dateStamp') F.dateStamp = !F.dateStamp;
    else if (name === 'singleFit') F.singleFit = value;
    else if (name === 'background') F.background = value;
    else if (name === 'subject') F.subject = !F.subject;
    const isOn = {
        shuffle: v => (v === '1') === F.shuffle,
        day: v => Boolean(F.days & (1 << Number(v))),
        enabled: () => F.enabled,
        recursive: () => F.recursive,
        composition: () => F.composition,
        dateStamp: () => F.dateStamp,
        singleFit: v => v === F.singleFit,
        background: v => v === F.background,
        subject: () => F.subject,
    }[name];
    // Chips that share a group (e.g. the album toggles) each keep their own state
    $$('.chip', group).forEach(c => { if (c.dataset.chip === name) c.classList.toggle('on', isOn(c.dataset.value)); });
    const bg = $('#backgroundField');
    if (bg) bg.hidden = !showBackground();
}

function onAction(action, el) {
    const actions = {
        'new-album': openNewAlbum,
        'add-folder': () => openBrowser(F.albumId),
        'add-icloud': openIcloudForm,
        'back-album': () => openAlbum(F.albumId),
        'use-folder': () => useFolder(el),
        'rescan': () => rescanAlbum(el),
        'compose': () => composeAlbum(el),
        'del-album': deleteAlbum,
        'del-source': () => deleteSource(Number(el.dataset.id)),
        'new-tv': () => openTvForm(null),
        'back-tv': () => openTv(F.tvId),
        'tv-edit': () => openTvForm(S.tvs.find(x => x.id === F.tvId)),
        'tv-refresh': () => tvCall(el, '/status', 'GET'),
        'tv-sync': () => tvCall(el, '/sync', 'POST', 'syncQueued'),
        'tv-toggle': () => toggleTv(el),
        'tv-gallery': () => openGallery(F.tvId),
        'pair': () => { el.textContent = t('pairing'); tvCall(el, '/pair', 'POST', 'paired'); },
        'del-tv': deleteTv,
        'gallery-delete': deleteGallerySelection,
        'new-slot': () => openSlot(null, Number(el.dataset.tvId)),
        'del-slot': deleteSlot,
    };
    if (actions[action]) actions[action]();
}

document.addEventListener('click', e => {
    if (e.target.closest('[data-close]')) { closeSheet(); return; }
    const help = e.target.closest('#sheetHelp');
    if (help) { toggleHelp(help); return; }
    const chip = e.target.closest('[data-chip]');
    if (chip) { onChip(chip); return; }
    const action = e.target.closest('[data-action]');
    if (action) { onAction(action.dataset.action, action); return; }
    const album = e.target.closest('[data-album]');
    if (album) { openAlbum(Number(album.dataset.album)); return; }
    const tv = e.target.closest('[data-tv]');
    if (tv) { openTv(Number(tv.dataset.tv)); return; }
    const slot = e.target.closest('[data-slot]');
    if (slot) { openSlot(Number(slot.dataset.slot)); return; }
    const page = e.target.closest('[data-page]');
    if (page) { openPage(Number(page.dataset.page)); return; }
    const image = e.target.closest('[data-image]');
    if (image) { toggleImage(image); return; }
    const browse = e.target.closest('[data-browse]');
    if (browse) { openBrowser(F.albumId, browse.dataset.browse); return; }
    const gsel = e.target.closest('[data-gsel]');
    if (gsel) { toggleGallerySelection(gsel); return; }
    const themeOpt = e.target.closest('[data-theme-opt]');
    if (themeOpt) {
        setTheme(themeOpt.dataset.themeOpt);
        $$('.chip', themeOpt.parentElement).forEach(c => c.classList.toggle('on', c === themeOpt));
        return;
    }
    const langOpt = e.target.closest('[data-lang-opt]');
    if (langOpt) { setLang(langOpt.dataset.langOpt); openSettings(); }
});

document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !$('#sheet').hidden) closeSheet();
});

$('#settingsBtn').onclick = openSettings;
$$('#tabs .tab').forEach(b => {
    b.onclick = () => {
        if (S.tab === b.dataset.tab) { window.scrollTo({ top: 0, behavior: 'smooth' }); return; }
        S.tab = b.dataset.tab;
        render();
        window.scrollTo({ top: 0 });
    };
});

// Top bar: turns solid and shows the small title once the large title scrolls out of view
function updateTopbar() {
    $('#topbar').classList.toggle('scrolled', window.scrollY > 36);
}
window.addEventListener('scroll', updateTopbar, { passive: true });
updateTopbar();

// Sheet: drag down from the header to close (mobile only)
(function sheetDrag() {
    const panel = $('.sheet-panel');
    const head = $('#sheetHead');
    let startY = null;
    let dy = 0;
    head.addEventListener('pointerdown', e => {
        if (e.target.closest('button') || window.matchMedia('(min-width: 720px)').matches) return;
        startY = e.clientY;
        dy = 0;
        panel.classList.add('dragging');
        panel.classList.remove('settle');
        head.setPointerCapture(e.pointerId);
    });
    head.addEventListener('pointermove', e => {
        if (startY == null) return;
        dy = Math.max(0, e.clientY - startY);
        panel.style.transform = `translateY(${dy}px)`;
    });
    const end = () => {
        if (startY == null) return;
        startY = null;
        panel.classList.remove('dragging');
        if (dy > 110) {
            closeSheet();
        } else {
            panel.classList.add('settle');
            panel.style.transform = '';
        }
    };
    head.addEventListener('pointerup', end);
    head.addEventListener('pointercancel', end);
})();

// Keep TV status fresh while the app is open
setInterval(() => {
    if (document.visibilityState === 'visible' && $('#sheet').hidden) reload('tvs').catch(() => {});
}, 60000);

setLang(S.lang, false);
loadAll();
