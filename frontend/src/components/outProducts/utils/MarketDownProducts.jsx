import React, { useState } from "react";
import { API_BASE_URL } from '../../services/adreses.jsx';
import { Button, CircularProgress, Box, Alert } from '@mui/material';

const MarketDownProducts = () => {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleDownload = async () => {
        setError(null);
        setIsLoading(true);

        try {
            const response = await fetch(`${API_BASE_URL}/market_down_products`, {
                method: "GET",
                headers: {
                    Accept: "application/zip",
                },
            });

            if (!response.ok) {
                const contentType = response.headers.get("content-type");

                if (contentType && contentType.includes("application/json")) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || `Помилка HTTP! статус: ${response.status}`);
                } else {
                    const errorText = await response.text();
                    console.error(errorText);
                    throw new Error(`Несподівана помилка! Статус: ${response.status}`);
                }
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = "market_down_products.zip";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

        } catch (e) {
            setError(e.message);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <Box sx={{ marginTop: '15px' }}>
            <Button
                variant="contained"
                color="primary"
                onClick={handleDownload}
                disabled={isLoading}
                fullWidth
                sx={{ padding: '15px' }}
                startIcon={isLoading ? <CircularProgress size={24} /> : null}
            >
                {isLoading ? 'Завантаження...' : 'Старт'}
            </Button>
            {error && (
                <Alert variant="outlined" severity="warning" sx={{ marginTop: '10px' }}>
                    {error}
                </Alert>
            )}
        </Box>
    );
};

export default MarketDownProducts;
