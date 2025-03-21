// frontend/src/components/redistribution/redistributionAPI.js

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'; // Використовуйте змінну середовища або '/api' за замовчуванням

export const fetchCategoriesHierarchy = async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/redistribution/categories-hierarchy`);
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error("Error fetching categories hierarchy:", error);
        throw error;
    }
};

export const fetchShopsWithIds = async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/redistribution/shops-with-ids`);
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error("Error fetching shops with IDs:", error);
        throw error;
    }
};

export const generateRedistributionPlan = async (payload) => {
    try {
        const response = await fetch(`${API_BASE_URL}/redistribution/generate-plan`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        });

        if (response.ok) {
            // Check content-type to differentiate between JSON message and file stream
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/zip')) {
                // If it's a zip file, return the blob for download
                return { type: 'file', data: await response.blob() };
            } else if (contentType && contentType.includes('application/json')) {
                // If it's a JSON message (e.g., "No plan generated")
                return { type: 'json', data: await response.json() };
            } else {
                throw new Error('Unexpected response content type.');
            }
        } else {
            // Handle HTTP errors (e.g., 400, 500)
            const errorData = await response.json();
            throw new Error(errorData.detail || errorData.error || `HTTP error! status: ${response.status}`);
        }
    } catch (error) {
        console.error("Error generating redistribution plan:", error);
        throw error;
    }
};