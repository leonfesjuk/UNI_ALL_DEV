import React, { useState } from "react";
import { API_BASE_URL } from '../../services/adreses.jsx';
import { Button, CircularProgress, Typography, Box, Alert } from '@mui/material';
import validateInputs from '../../services/validateDates.jsx';
import DateInputForm from '../../services/dateInputForm'; 

const DownloadInsurance = () => {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");

    const handleDownload = async () => {
        setError(null);
        setIsLoading(true);
        try {
            const response = await fetch(`${API_BASE_URL}/insurance_balance`, {
                method: "POST",
                headers: {
          "Content-Type": "application/json",
          Accept:
            "application/zip",
                },
                body: JSON.stringify({
                   date_start: startDate,
                    date_finish: endDate, 
                }),
            });

            const blob = await response.blob();
            const contentType = response.headers.get("content-type");
            if (!contentType || !contentType.includes("application/zip")) {
                throw new Error("Unexpected response format. Not a ZIP file.");
            }

            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = "insurance.zip";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        }   catch (err) {
            console.error('Помилка запиту:', err);
            setError(err.message);
        }   finally {
            setIsLoading(false);
        }

    };

    return (
        <DateInputForm
            startDate={startDate}
            setStartDate={setStartDate}
            endDate={endDate}
            setEndDate={setEndDate}
            handleDownload={handleDownload}
            isLoading={isLoading}
            error={error}
        />
    );
};

export default DownloadInsurance
