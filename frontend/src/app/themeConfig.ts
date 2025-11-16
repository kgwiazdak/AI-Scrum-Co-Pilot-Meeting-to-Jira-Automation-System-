import type {PaletteMode} from '@mui/material';
import {createTheme} from '@mui/material';

export const buildTheme = (mode: PaletteMode) =>
    createTheme({
        palette: {
            mode,
            primary: {
                main: '#0066ff',
            },
            background: {
                default: mode === 'light' ? '#f4f6fb' : '#050708',
                paper: mode === 'light' ? '#ffffff' : '#10151c',
            },
        },
        shape: {
            borderRadius: 12,
        },
        typography: {
            fontFamily: "'Inter', 'IBM Plex Sans', system-ui, sans-serif",
        },
        components: {
            MuiButton: {
                defaultProps: {
                    variant: 'contained',
                },
                styleOverrides: {
                    root: {
                        textTransform: 'none',
                        boxShadow: 'none',
                    },
                },
            },
        },
    });

export const getPreferredMode = (): PaletteMode => {
    if (typeof window === 'undefined' || !window.matchMedia) {
        return 'light';
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light';
};
