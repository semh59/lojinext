import {
  getPreferencesApiV1PreferencesModulGet,
  savePreferenceApiV1PreferencesPost,
  deletePreferenceApiV1PreferencesPrefIdDelete,
  setDefaultPreferenceApiV1PreferencesPrefIdDefaultPost,
} from "../generated/api/preferences/preferences";

export interface Preference {
  id: number;
  modul: string;
  ayar_tipi: string;
  deger: any;
  ad?: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface PreferenceCreate {
  modul: string;
  ayar_tipi: string;
  deger: any;
  ad?: string;
  is_default?: boolean;
}

export const preferenceService = {
  getPreferences: async (modul: string, ayar_tipi?: string) => {
    const response = await getPreferencesApiV1PreferencesModulGet(
      modul,
      ayar_tipi ? { ayar_tipi } : undefined,
    );
    return (response as unknown as { items: Preference[] }).items;
  },

  savePreference: async (data: PreferenceCreate) => {
    const response = await savePreferenceApiV1PreferencesPost(
      data as unknown as Parameters<
        typeof savePreferenceApiV1PreferencesPost
      >[0],
    );
    return response as unknown as Preference;
  },

  deletePreference: async (id: number) => {
    const response = await deletePreferenceApiV1PreferencesPrefIdDelete(id);
    return response;
  },

  setDefault: async (id: number) => {
    const response =
      await setDefaultPreferenceApiV1PreferencesPrefIdDefaultPost(id);
    return response;
  },
};
