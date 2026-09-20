/**
 * Farmer-page text in English, Kannada and Hindi.
 *
 * STATUS: Kannada and Hindi are DRAFT translations written for the prototype.
 * They must be reviewed by native speakers (ideally an agronomist or KVK staff)
 * before use with farmers. In production these come from the reviewed template
 * store shared with the WhatsApp/SMS service (docs/DELIVERY_BRIEF.md §5).
 */
export type Lang = "en" | "kn" | "hi";
export const LANGS: { key: Lang; label: string; locale: string }[] = [
  { key: "kn", label: "ಕನ್ನಡ", locale: "kn-IN" },
  { key: "hi", label: "हिन्दी", locale: "hi-IN" },
  { key: "en", label: "English", locale: "en-IN" },
];
export const locale = (l: Lang) => LANGS.find((x) => x.key === l)!.locale;

type Dict = Record<Lang, string>;
const t = (en: string, kn: string, hi: string): Dict => ({ en, kn, hi });

export const CROP_NAME: Record<string, Dict> = {
  ragi: t("Ragi", "ರಾಗಿ", "रागी"),
  maize: t("Maize", "ಮೆಕ್ಕೆಜೋಳ", "मक्का"),
  pigeonpea: t("Tur (pigeonpea)", "ತೊಗರಿ", "अरहर"),
  rice: t("Paddy", "ಭತ್ತ", "धान"),
  soybean: t("Soybean", "ಸೋಯಾಬೀನ್", "सोयाबीन"),
  cotton: t("Cotton", "ಹತ್ತಿ", "कपास"),
  groundnut: t("Groundnut", "ಶೇಂಗಾ", "मूंगफली"),
  bajra: t("Bajra", "ಸಜ್ಜೆ", "बाजरा"),
  jowar: t("Jowar", "ಜೋಳ", "ज्वार"),
};

export const UI = {
  forYourField: t("Advice for your field", "ನಿಮ್ಮ ಹೊಲಕ್ಕೆ ಸಲಹೆ", "आपके खेत के लिए सलाह"),
  crop: t("Your crop", "ನಿಮ್ಮ ಬೆಳೆ", "आपकी फसल"),
  next4: t("Next 4 weeks", "ಮುಂದಿನ 4 ವಾರಗಳು", "अगले 4 हफ्ते"),
  whatToDo: t("What to do", "ಏನು ಮಾಡಬೇಕು", "क्या करें"),
  week: t("Week", "ವಾರ", "हफ्ता"),
  drySpell: t("Dry spell", "ಒಣ ಹವೆ", "सूखा दौर"),
  heavyRain: t("Heavy rain", "ಭಾರೀ ಮಳೆ", "भारी बारिश"),
  usually: t("usually", "ಸಾಮಾನ್ಯವಾಗಿ", "आम तौर पर"),
  inTen: t("{n} in 10", "10ರಲ್ಲಿ {n}", "10 में {n}"),
  callHelp: t("Talk to an expert (free)", "ತಜ್ಞರೊಂದಿಗೆ ಮಾತನಾಡಿ (ಉಚಿತ)", "विशेषज्ञ से बात करें (मुफ़्त)"),
  kcc: t("Kisan Call Centre · 1800-180-1551", "ಕಿಸಾನ್ ಕಾಲ್ ಸೆಂಟರ್ · 1800-180-1551", "किसान कॉल सेंटर · 1800-180-1551"),
  issued: t("Updated", "ನವೀಕರಿಸಲಾಗಿದೆ", "अपडेट"),
  source: t("Based on IMD rainfall data · CMRI v1.0", "IMD ಮಳೆ ಮಾಹಿತಿ ಆಧಾರಿತ · CMRI v1.0", "IMD वर्षा आंकड़ों पर आधारित · CMRI v1.0"),
  arrived: t("The monsoon has arrived here.", "ಇಲ್ಲಿ ಮುಂಗಾರು ಆರಂಭವಾಗಿದೆ.", "यहाँ मानसून आ चुका है।"),
  holding: t("Sowing rain came on {d}. No long dry break yet.", "{d}ರಂದು ಬಿತ್ತನೆ ಮಳೆ ಬಂದಿದೆ. ಇನ್ನೂ ದೀರ್ಘ ಒಣ ಅವಧಿ ಬಂದಿಲ್ಲ.", "{d} को बुवाई लायक बारिश हुई। अभी तक लंबा सूखा दौर नहीं आया।"),
  failed: t("Rain on {d} was followed by a long dry spell (false start).", "{d}ರ ಮಳೆಯ ನಂತರ ದೀರ್ಘ ಒಣ ಅವಧಿ ಬಂತು (ಸುಳ್ಳು ಆರಂಭ).", "{d} की बारिश के बाद लंबा सूखा दौर आया (झूठी शुरुआत)।"),
  pending: t("The monsoon hasn't properly started here yet.", "ಇಲ್ಲಿ ಮುಂಗಾರು ಇನ್ನೂ ಸರಿಯಾಗಿ ಆರಂಭವಾಗಿಲ್ಲ.", "यहाँ मानसून अभी ठीक से शुरू नहीं हुआ है।"),
  notFound: t("We couldn't find this area.", "ಈ ಪ್ರದೇಶ ಸಿಗಲಿಲ್ಲ.", "यह क्षेत्र नहीं मिला।"),
  offline: t("No connection. Showing the last saved advice.", "ಸಂಪರ್ಕ ಇಲ್ಲ. ಕೊನೆಯ ಉಳಿಸಿದ ಸಲಹೆ ತೋರಿಸಲಾಗುತ್ತಿದೆ.", "कनेक्शन नहीं है। आखिरी सहेजी गई सलाह दिखाई जा रही है।"),
};

/** Verdict and actions per advisory template. */
export const VERDICT: Record<string, { title: Dict; actions: Dict[] }> = {
  DELAY_SOWING: {
    title: t("Wait to sow", "ಬಿತ್ತನೆ ಮುಂದೂಡಿ", "अभी बुवाई न करें"),
    actions: [
      t("Don't sow on the first showers.", "ಮೊದಲ ಮಳೆಗೆ ಬಿತ್ತನೆ ಮಾಡಬೇಡಿ.", "पहली बारिश पर बुवाई न करें।"),
      t("Sow after {d}, or when the soil is wet to a hand's depth.", "{d}ರ ನಂತರ ಅಥವಾ ಮಣ್ಣು ಒಂದು ಕೈ ಆಳದವರೆಗೆ ತೇವವಾದಾಗ ಬಿತ್ತಿ.", "{d} के बाद बोएं, या जब मिट्टी एक हाथ की गहराई तक गीली हो।"),
      t("Keep seed and fertiliser ready.", "ಬೀಜ ಮತ್ತು ಗೊಬ್ಬರ ಸಿದ್ಧವಾಗಿಡಿ.", "बीज और खाद तैयार रखें।"),
    ],
  },
  SOW_NOW: {
    title: t("Good time to sow", "ಬಿತ್ತನೆಗೆ ಸೂಕ್ತ ಸಮಯ", "बुवाई का सही समय"),
    actions: [
      t("Sow when the coming rain wets the soil.", "ಬರುವ ಮಳೆಗೆ ಮಣ್ಣು ತೇವವಾದಾಗ ಬಿತ್ತಿ.", "आने वाली बारिश से मिट्टी गीली होने पर बोएं।"),
      t("No unusual dry spell is expected after it.", "ಅದರ ನಂತರ ಅಸಾಮಾನ್ಯ ಒಣ ಅವಧಿ ನಿರೀಕ್ಷಿಸಿಲ್ಲ.", "उसके बाद असामान्य सूखे दौर की आशंका नहीं है।"),
    ],
  },
  SWITCH_CROP: {
    title: t("Monsoon is late: plan ahead", "ಮುಂಗಾರು ತಡವಾಗಿದೆ: ಮುಂದಾಲೋಚನೆ ಮಾಡಿ", "मानसून देर से है: आगे की योजना बनाएं"),
    actions: [
      t("The monsoon is {w} weeks late here.", "ಇಲ್ಲಿ ಮುಂಗಾರು {w} ವಾರ ತಡವಾಗಿದೆ.", "यहाँ मानसून {w} हफ्ते देर से है।"),
      t("Choose a short-duration variety.", "ಅಲ್ಪಾವಧಿ ತಳಿಯನ್ನು ಆರಿಸಿ.", "कम अवधि वाली किस्म चुनें।"),
      t("Ask your agriculture officer about a contingency crop.", "ಪರ್ಯಾಯ ಬೆಳೆ ಬಗ್ಗೆ ಕೃಷಿ ಅಧಿಕಾರಿಯನ್ನು ಕೇಳಿ.", "वैकल्पिक फसल के बारे में कृषि अधिकारी से पूछें।"),
    ],
  },
  PREPARE_IRRIGATION: {
    title: t("Seedlings at risk: arrange water", "ಸಸಿಗಳಿಗೆ ಅಪಾಯ: ನೀರಿನ ವ್ಯವಸ್ಥೆ ಮಾಡಿ", "पौधों को खतरा: पानी का इंतज़ाम करें"),
    actions: [
      t("A long dry spell is likely soon.", "ಶೀಘ್ರದಲ್ಲೇ ದೀರ್ಘ ಒಣ ಅವಧಿ ಸಾಧ್ಯತೆ ಇದೆ.", "जल्द ही लंबा सूखा दौर आने की संभावना है।"),
      t("Plan one protective irrigation.", "ಒಂದು ರಕ್ಷಣಾತ್ಮಕ ನೀರಾವರಿ ಯೋಜಿಸಿ.", "एक बचाव सिंचाई की योजना बनाएं।"),
      t("Cover the soil with mulch.", "ಮಣ್ಣನ್ನು ಹೊದಿಕೆಯಿಂದ ಮುಚ್ಚಿ.", "मिट्टी को पलवार (मल्च) से ढकें।"),
    ],
  },
  DRY_SPELL_CONSERVE_MOISTURE: {
    title: t("Dry spell coming: save soil moisture", "ಒಣ ಅವಧಿ ಬರಲಿದೆ: ಮಣ್ಣಿನ ತೇವಾಂಶ ಉಳಿಸಿ", "सूखा दौर आने वाला है: मिट्टी की नमी बचाएं"),
    actions: [
      t("Mulch between rows.", "ಸಾಲುಗಳ ನಡುವೆ ಹೊದಿಕೆ ಹಾಕಿ.", "कतारों के बीच पलवार बिछाएं।"),
      t("Hoe lightly to break the soil crust.", "ಮಣ್ಣಿನ ಪದರ ಒಡೆಯಲು ಲಘುವಾಗಿ ಕುಂಟೆ ಹೊಡೆಯಿರಿ.", "मिट्टी की पपड़ी तोड़ने के लिए हल्की गुड़ाई करें।"),
      t("Hold off on fertiliser until it rains.", "ಮಳೆ ಬರುವವರೆಗೆ ಗೊಬ್ಬರ ಹಾಕಬೇಡಿ.", "बारिश होने तक खाद न डालें।"),
    ],
  },
  HEAVY_RAIN_PROTECT: {
    title: t("Heavy rain likely", "ಭಾರೀ ಮಳೆ ಸಾಧ್ಯತೆ", "भारी बारिश की संभावना"),
    actions: [
      t("Clear field drains.", "ಹೊಲದ ಕಾಲುವೆಗಳನ್ನು ಸ್ವಚ್ಛಗೊಳಿಸಿ.", "खेत की नालियाँ साफ़ करें।"),
      t("Postpone spraying and fertiliser.", "ಸಿಂಪಡಣೆ ಮತ್ತು ಗೊಬ್ಬರ ಮುಂದೂಡಿ.", "छिड़काव और खाद डालना टालें।"),
    ],
  },
  NONE: {
    title: t("No special action this week", "ಈ ವಾರ ವಿಶೇಷ ಕ್ರಮ ಬೇಕಿಲ್ಲ", "इस हफ्ते कोई विशेष कदम नहीं"),
    actions: [t("Continue normal field work.", "ಸಾಮಾನ್ಯ ಕೃಷಿ ಕೆಲಸ ಮುಂದುವರಿಸಿ.", "खेत का सामान्य काम जारी रखें।")],
  },
};

export const fill = (s: string, vars: Record<string, string | number>) =>
  s.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ""));

/** Digits in the reader's script: Kannada and Hindi farmers read native numerals too,
 *  but Western digits are standard in Indian print and SMS, so keep them. */
export const inTen = (p: number, l: Lang) => fill(UI.inTen[l], { n: Math.max(0, Math.min(10, Math.round(p * 10))) });
