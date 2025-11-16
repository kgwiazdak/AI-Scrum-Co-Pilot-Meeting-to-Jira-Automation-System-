import {createContext, useContext} from 'react';
import type {PaletteMode} from '@mui/material';

export type ThemeModeContextValue = {
    mode: PaletteMode;
    toggleMode: () => void;
};

export const ThemeModeContext = createContext<ThemeModeContextValue>({
    mode: 'light',
    toggleMode: () => undefined,
});

export const useThemeMode = () => useContext(ThemeModeContext);
