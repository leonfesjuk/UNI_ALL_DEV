// frontend/src/components/redistribution/RedistributionPage.jsx
import React, { useState, useEffect } from 'react';
import {
    Container,
    Typography,
    Box,
    TextField,
    Button,
    CircularProgress,
    Alert,
    FormControl,
    FormGroup,
    FormControlLabel,
    Checkbox,
    Grid,
    Paper,
} from '@mui/material';
import DateInputForm from '../services/dateInputForm';
import validateInputs from '../services/validateDates';
import {
    fetchCategoriesHierarchy,
    fetchShopsWithIds,
    generateRedistributionPlan
} from './redistributionAPI';


const RedistributionPage = () => {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [message, setMessage] = useState(null);

    const [dateStart, setDateStart] = useState('');
    const [dateFinish, setDateFinish] = useState('');
    const [daysOfAnalysis, setDaysOfAnalysis] = useState(7);
    const [minSurplusCoefficient, setMinSurplusCoefficient] = useState(1.2);

    const [allShops, setAllShops] = useState([]);
    const [donorMarketsIds, setDonorMarketsIds] = useState([]);
    const [recipientMarketsIds, setRecipientMarketsIds] = useState([]);

    const [categoriesHierarchy, setCategoriesHierarchy] = useState([]);
    const [selectedLowestCategoriesNames, setSelectedLowestCategoriesNames] = useState([]);

    useEffect(() => {
        const loadInitialData = async () => {
            setIsLoading(true);
            setError(null);
            try {
                const [shopsData, categoriesData] = await Promise.all([
                    fetchShopsWithIds(),
                    fetchCategoriesHierarchy()
                ]);
                setAllShops(shopsData);
                setCategoriesHierarchy(categoriesData);
            } catch (err) {
                setError(err.message || "Не вдалося завантажити початкові дані.");
            } finally {
                setIsLoading(false);
            }
        };
        loadInitialData();
    }, []);

    const getUniqueLowestCategories = (categories) => {
        // Backend now returns ONLY unique groups (Відділи)
        // Just extract the group field from each category
        return categories
            .filter(cat => cat.group && cat.group !== '')
            .map(cat => cat.group);
    };

    const uniqueLowestCategories = getUniqueLowestCategories(categoriesHierarchy);

    const handleSubmit = async () => {
        setError(null);
        setMessage(null);

        if (!validateInputs(dateStart, dateFinish, null, setError)) {
            return;
        }

        if (donorMarketsIds.length === 0) {
            setError('Будь ласка, виберіть хоча б один магазин-донор.');
            return;
        }
        if (recipientMarketsIds.length === 0) {
            setError('Будь ласка, виберіть хоча б один магазин-реципієнт.');
            return;
        }
        if (selectedLowestCategoriesNames.length === 0) {
            setError('Будь ласка, виберіть хоча б одну групу товарів.');
            return;
        }
        if (isNaN(parseInt(daysOfAnalysis)) || parseInt(daysOfAnalysis) < 1) {
            setError('Період аналізу (дні) має бути числом більше або рівним 1.');
            return;
        }
        if (isNaN(parseFloat(minSurplusCoefficient)) || parseFloat(minSurplusCoefficient) <= 0) {
            setError('Мінімальний коефіцієнт надлишку має бути числом більше 0.');
            return;
        }

        setIsLoading(true);

        const payload = {
            date_start: dateStart,
            date_finish: dateFinish,
            days_of_analysis: parseInt(daysOfAnalysis),
            min_surplus_coefficient: parseFloat(minSurplusCoefficient),
            donor_markets_ids: donorMarketsIds,
            recipient_markets_ids: recipientMarketsIds,
            selected_lowest_categories_names: selectedLowestCategoriesNames,
        };

        try {
            const result = await generateRedistributionPlan(payload);
            if (result.type === 'file') {
                const url = window.URL.createObjectURL(new Blob([result.data]));
                const link = document.createElement('a');
                link.href = url;
                link.setAttribute('download', 'Redistribution_Plan.zip');
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                window.URL.revokeObjectURL(url);
                setMessage("План перерозподілу успішно згенеровано та завантажено!");
            } else if (result.type === 'json' && result.data.message) {
                setMessage(result.data.message);
            } else {
                setError("Невідома відповідь від сервера.");
            }
        } catch (e) {
            setError(e.message);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <Container component={Paper} elevation={3} sx={{
            width: '100%',
            minHeight: 'calc(100vh - 40px)',
            display: 'flex',
            flexDirection: 'column',
            margin: '0',
            backgroundColor: 'transparent',
            p: 3,
            boxSizing: 'border-box',
        }}>
            <Grid container spacing={3} sx={{ height: '100%' }}>
                <Grid item xs={12}>
                    <Box sx={{ textAlign: 'center', mb: 3 }}>
                        <Typography variant="h5" gutterBottom color="white">
                            Генерація плану перерозподілу товарів
                        </Typography>
                        {error && (
                            <Typography color="error" sx={{ mb: 2 }}>
                                {error}
                            </Typography>
                        )}
                        <Grid container spacing={2} justifyContent="center" alignItems="center">
                            <Grid item xs={12} sm={6} md={4}>
                                <DateInputForm
                                    startDate={dateStart} setStartDate={setDateStart}
                                    endDate={dateFinish} setEndDate={setDateFinish}
                                    handleDownload={handleSubmit} isLoading={isLoading} error={null}
                                />
                            </Grid>
                            <Grid item xs={12} sm={6} md={4}>
                                <Typography variant="subtitle1" color="white" sx={{ mb: 1, textAlign: 'left' }}>Період аналізу (дні)</Typography>
                                <TextField
                                    type="number"
                                    value={daysOfAnalysis}
                                    onChange={(e) => setDaysOfAnalysis(e.target.value)}
                                    fullWidth
                                    required
                                    inputProps={{ min: 1 }}
                                    sx={{
                                        mb: 2,
                                        '& .MuiInputBase-root': {
                                            backgroundColor: 'white',
                                            borderRadius: '4px',
                                        },
                                        '& .MuiInputBase-input': { color: 'black' },
                                        '& .MuiOutlinedInput-notchedOutline': { borderColor: 'white' },
                                        '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: 'white' },
                                        '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: 'white' },
                                    }}
                                />
                                <Typography variant="subtitle1" color="white" sx={{ mb: 1, textAlign: 'left' }}>Мінімальний коефіцієнт надлишку</Typography>
                                <TextField
                                    type="number"
                                    step="0.1"
                                    value={minSurplusCoefficient}
                                    onChange={(e) => setMinSurplusCoefficient(e.target.value)}
                                    fullWidth
                                    required
                                    inputProps={{ min: 0.1 }}
                                    sx={{
                                        '& .MuiInputBase-root': {
                                            backgroundColor: 'white',
                                            borderRadius: '4px',
                                        },
                                        '& .MuiInputBase-input': { color: 'black' },
                                        '& .MuiOutlinedInput-notchedOutline': { borderColor: 'white' },
                                        '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: 'white' },
                                        '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: 'white' },
                                    }}
                                />
                            </Grid>
                            <Grid item xs={12} sm={12} md={4}>
                            </Grid>
                        </Grid>
                    </Box>
                </Grid>

                <Grid item xs={12} sx={{ flexGrow: 1, display: 'flex' }}>
                    <Grid container spacing={3} sx={{ height: '100%' }}>
                        <Grid item xs={12} md={4} sx={{ display: 'flex', flexDirection: 'column' }}>
                            <Typography variant="subtitle1" color="white" sx={{ mb: 1, textAlign: 'left' }}>Магазини-донори</Typography>
                            <FormControl component="fieldset" sx={{ flexGrow: 1, minWidth: '250px', p: 1, border: '1px solid #ccc', borderRadius: '5px', backgroundColor: '#f5f5f5' }}>
                                {allShops.length > 0 ? (
                                    <FormGroup sx={{ flexGrow: 1, overflowY: 'auto' }}>
                                        {allShops.map((shop) => (
                                            <FormControlLabel
                                                key={shop.id}
                                                control={
                                                    <Checkbox
                                                        checked={donorMarketsIds.includes(shop.id)}
                                                        onChange={() => setDonorMarketsIds(prev =>
                                                            prev.includes(shop.id) ? prev.filter(id => id !== shop.id) : [...prev, shop.id]
                                                        )}
                                                        value={shop.id}
                                                        sx={{ color: 'grey.700' }}
                                                    />
                                                }
                                                label={shop.name}
                                                sx={{ color: 'black' }}
                                            />
                                        ))}
                                    </FormGroup>
                                ) : (
                                    !isLoading && <Typography sx={{ color: 'black' }}>Магазини відсутні</Typography>
                                )}
                            </FormControl>
                        </Grid>

                        <Grid item xs={12} md={4} sx={{ display: 'flex', flexDirection: 'column' }}>
                            <Typography variant="subtitle1" color="white" sx={{ mb: 1, textAlign: 'left' }}>Магазини-реципієнти</Typography>
                            <FormControl component="fieldset" sx={{ flexGrow: 1, minWidth: '250px', p: 1, border: '1px solid #ccc', borderRadius: '5px', backgroundColor: '#f5f5f5' }}>
                                {allShops.length > 0 ? (
                                    <FormGroup sx={{ flexGrow: 1, overflowY: 'auto' }}>
                                        {allShops.map((shop) => (
                                            <FormControlLabel
                                                key={shop.id}
                                                control={
                                                    <Checkbox
                                                        checked={recipientMarketsIds.includes(shop.id)}
                                                        onChange={() => setRecipientMarketsIds(prev =>
                                                            prev.includes(shop.id) ? prev.filter(id => id !== shop.id) : [...prev, shop.id]
                                                        )}
                                                        value={shop.id}
                                                        sx={{ color: 'grey.700' }}
                                                    />
                                                }
                                                label={shop.name}
                                                sx={{ color: 'black' }}
                                            />
                                        ))}
                                    </FormGroup>
                                ) : (
                                    !isLoading && <Typography sx={{ color: 'black' }}>Магазини відсутні</Typography>
                                )}
                            </FormControl>
                        </Grid>

                        <Grid item xs={12} md={4} sx={{ display: 'flex', flexDirection: 'column' }}>
                            <Typography variant="subtitle1" color="white" sx={{ mb: 1, textAlign: 'left' }}>Групи товарів (Відділ)</Typography>
                            <FormControl component="fieldset" sx={{ flexGrow: 1, minWidth: '250px', p: 1, border: '1px solid #ccc', borderRadius: '5px', backgroundColor: '#f5f5f5' }}>
                                {uniqueLowestCategories.length > 0 ? (
                                    <FormGroup sx={{ flexGrow: 1, overflowY: 'auto' }}>
                                        {uniqueLowestCategories.map((categoryName) => (
                                            <FormControlLabel
                                                key={categoryName}
                                                control={
                                                    <Checkbox
                                                        checked={selectedLowestCategoriesNames.includes(categoryName)}
                                                        onChange={() => setSelectedLowestCategoriesNames(prev =>
                                                            prev.includes(categoryName) ? prev.filter(name => name !== categoryName) : [...prev, categoryName]
                                                        )}
                                                        value={categoryName}
                                                        sx={{ color: 'grey.700' }}
                                                    />
                                                }
                                                label={categoryName}
                                                sx={{ color: 'black' }}
                                            />
                                        ))}
                                    </FormGroup>
                                ) : (
                                    !isLoading && <Typography sx={{ color: 'black' }}>Групи товарів відсутні</Typography>
                                )}
                            </FormControl>
                        </Grid>
                    </Grid>
                </Grid>


                {message && (
                    <Alert severity="success" sx={{ mt: 3 }}>
                        {message}
                    </Alert>
                )}
            </Grid>
        </Container>
    );
};

export default RedistributionPage;