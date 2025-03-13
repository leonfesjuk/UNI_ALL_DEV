import React, { useState } from "react";
import { API_BASE_URL } from '../../services/adreses.jsx';
import DateInputForm from '../../services/dateInputForm'; 


const ArchiveProductsStart = () => {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");
   
    const handleDownload = async () => {
        setError(null);

       
        
        setIsLoading(true);

        try {
            const response = await fetch(`${API_BASE_URL}/archive_products`, {
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

            if (!response.ok) {
                const contentType = response.headers.get("content-type");

                if (contentType && contentType.includes("application/json")) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || `Помилка HTTP! статус: ${response.status}`);
                } else {
                    const errorText = await response.text()
                    console.error(errorText);
                    throw new Error(`Несподівана помилка! Статус: ${response.status}`);
                }
            }

            const blob = await response.blob();
            console.log("Розмір Blob:", blob.size); // Перевірка розміру
            console.log("Тип Blob:", blob.type); // Перевірка типу
            const contentType = response.headers.get("content-type");
            if (!contentType || !contentType.includes("application/zip")) {
                throw new Error("Unexpected response format. Not a ZIP file.");
            }

            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            if (!a) {
                throw new Error("Failed to create a link element.");
            };
            a.href = url;
            a.download = "outProducts.zip";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            
        } catch (e) {
            setError(e.message);
        } finally {
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

export default ArchiveProductsStart;
