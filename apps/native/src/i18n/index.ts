import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

// Spanish translations following exactly the es.json definitions of Actinver Advisor
const esMX = {
  nav: {
    label: "Navegación principal",
    advisor: "Tino",
    demo: "Demo avatar"
  },
  advisor: {
    title: "Tino",
    subtitle: "Le ayudo a entender su portafolio, explorar instrumentos y preparar lo que necesite.",
    greeting: "Hola. ¿Qué le gustaría revisar hoy?",
    loading: "Conectando con Tino...",
    empty: "Pregunte sobre su portafolio, el mercado o dónde invertir.",
    chips: {
      portfolio: "¿Cómo va mi portafolio este mes?",
      products: "¿Qué ETFs de deuda me convienen?",
      retire: "¿Cuánto necesito para retirarme en 20 años?"
    },
    input_label: "Mensaje para Tino",
    input_placeholder: "Escriba su pregunta",
    send: "Enviar",
    you: "Usted",
    assistant: "Tino",
    portfolio_title: "Resumen de portafolio",
    attribution_title: "Atribución del periodo",
    sources_title: "Fuentes",
    as_of: "Al {{date}}",
    mode_chat: "Chat",
    mode_video: "Video",
    view_mode_label: "Modo de vista",
    avatar_hide: "Ocultar avatar",
    avatar_starting: "Iniciando avatar...",
    avatar_connecting: "Conectando...",
    avatar_ended: "La sesión de video terminó. Puede volver a activarla.",
    avatar_error: "No se pudo iniciar la sesión de video.",
    mic_on: "Activar micro",
    mic_off: "Silenciar micro",
    mic_unavailable: "Micrófono no disponible: escriba sus mensajes.",
    interrupt: "Interrumpir",
    thinking: "Pensando...",
    kill_switch: "El asesor está temporalmente deshabilitado. Intente más tarde.",
    dismiss: "Cerrar",
    error_unknown: "Ocurrió un error. Intente de nuevo.",
    error_event: "Tino no pudo responder ({{code}}). Intente de nuevo.",
    market_value: "Valor de mercado",
    period_return: "Rendimiento",
    contributions: "Contribuciones",
    citations: "Fuentes",
    as_of_label: "Corte",
    today: "hoy"
  },
  live: {
    title: "Consulta con Tino",
    subtitle: "Tu asesor de IA financiero",
    greeting: "Hola, soy Tino. Pregúntame sobre tu portafolio o en qué invertir.",
    suggestion_1: "ETFs de deuda de bajo riesgo",
    suggestion_2: "¿Cómo empiezo a invertir?",
    suggestion_3: "Revisar mi portafolio",
    day_today: "Hoy",
    day_yesterday: "Ayer",
    start: "Iniciar conversación",
    starting: "Iniciando...",
    connecting: "Conectando...",
    transcript: "Transcripción",
    input_label: "Mensaje para el avatar",
    input_placeholder: "Escribe un mensaje",
    send: "Enviar",
    end: "Terminar",
    interrupt: "Interrumpir",
    avatar_talking: "Avatar hablando",
    listening: "Escuchando...",
    state_connected: "En vivo",
    state_disconnecting: "Cerrando",
    state_offline: "Sin conexión",
    quality_poor: "Señal débil",
    mic_mute: "Silenciar micro",
    mic_unmute: "Activar micro",
    mic_unavailable: "Micrófono no disponible: escribe tus mensajes.",
    mic_permission_title: "Micrófono",
    mic_permission_message: "Tino necesita el micrófono para la conversación por voz.",
    avatar: "Tino",
    ended_by_server: "La sesión se cerró. Puedes iniciar otra.",
    error_unknown: "Error desconocido",
    expand: "Pantalla completa",
    collapse: "Salir de pantalla completa"
  }
};

i18n
  .use(initReactI18next)
  .init({
    resources: {
      'es-MX': {
        translation: esMX,
      },
      es: {
        translation: esMX,
      }
    },
    lng: 'es-MX',
    fallbackLng: 'es-MX',
    interpolation: {
      escapeValue: false, // React already safeguards against XSS
    },
  });

export default i18n;
