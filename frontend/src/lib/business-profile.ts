const commercialAddress = "Carretera de Porzuna, km 2,8, 13004 Ciudad Real";

export const businessProfile = {
  name: "AUREA Obras y Servicios",
  phone: "602 463 840",
  phoneHref: "tel:+34602463840",
  email: "obrasyserviciosaurea@gmail.com",
  emailHref: "mailto:obrasyserviciosaurea@gmail.com",
  location: {
    city: "Ciudad Real",
    lineOne: "Carretera de Porzuna, km 2,8",
    lineTwo: "13004 Ciudad Real",
    mapsUrl: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(commercialAddress)}`,
  },
} as const;
