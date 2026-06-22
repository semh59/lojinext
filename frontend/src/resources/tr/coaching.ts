export const coachingPageText = {
  heading: "Koçluk Modülü",
  description: "AI destekli şoför davranış analizi ve öneriler.",
  emptyDriverList: "Aktif şoför bulunamadı.",
  selectDriverHint: "Detay görmek için sol panelden bir şoför seçin.",
  sourceLlm: "AI tarafından üretildi",
  sourceFallback: "Kural tabanlı (LLM yedeği)",
  refresh: "Yenile",
  errorLoad: "Öneriler yüklenemedi",
  emptyInsights: "Bu şoför için aktif öneri yok",
} as const;

export const coachingCategoryLabels: Record<string, string> = {
  yakit_yonetimi: "Yakıt Yönetimi",
  guzergah_tercihi: "Güzergah Tercihi",
  sofor_pratigi: "Sürüş Pratiği",
  diger: "Diğer",
} as const;

export const coachingPriorityLabels: Record<string, string> = {
  low: "Düşük",
  medium: "Orta",
  high: "Yüksek",
} as const;

export const sendCoachingDialogText = {
  title: "Telegram ile Koçluk Gönder",
  subtitle: (name: string) => `${name} adlı şoföre`,
  messageLabel: "Mesaj",
  messagePlaceholder: "Önerinizi düzenleyin...",
  minLength: "Mesaj en az 10 karakter olmalı.",
  maxLength: "Mesaj 1000 karakteri geçemez.",
  sendButton: "Telegram'a Gönder",
  cancel: "İptal",
  successTitle: "Gönderildi",
  successMessage: "Mesaj Telegram üzerinden iletildi.",
  errorTitle: "Hata",
  errorMessage: "Mesaj gönderilemedi.",
  notRegisteredTitle: "Şoför Telegram'a kayıtlı değil",
  notRegisteredMessage:
    "Bu şoför Telegram bot ile eşleşmemiş; mesaj gönderilemez.",
} as const;

export const coachingDriverListText = {
  heading: "Şoförler",
  searchPlaceholder: "Ara...",
  aktifOnly: "Sadece aktif",
} as const;
