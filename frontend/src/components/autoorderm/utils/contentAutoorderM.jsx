import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../../services/adreses.jsx';
import DateInputForm from '../../services/dateInputForm';
import validateInputs from '../../services/validateDates.jsx';
import {
  Checkbox,
  FormControl,
  FormControlLabel,
  FormGroup,
  FormLabel,
  Paper,
  Typography,
  Box,
  Grid,
} from '@mui/material';

const AnalysisForm = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [days_of_order, setOrderDays] = useState('');
  const [groups, setGroups] = useState([]);
  const [selectedGroups, setSelectedGroups] = useState([]);
  const [markets, setMarkets] = useState([]);
  const [selectedMarkets, setSelectedMarkets] = useState([]);
  const [todayStocsMode, setTodayStocsMode] = useState(false);


  useEffect(() => {
    const fetchMarkets = async () => {
      try {
        setIsLoading(true);
        const response = await fetch(`${API_BASE_URL}/markets_list`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        });
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || `Помилка HTTP! статус: ${response.status}`);
        }
        const data = await response.json();
        setMarkets(data);
      } catch (e) {
        setError(e.message);
      } finally {
        setIsLoading(false);
      }
    };
    fetchMarkets();
  }, []);

  useEffect(() => {
    const fetchGroups = async () => {
      try {
        setIsLoading(true);
        const response = await fetch(`${API_BASE_URL}/groups`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || `Помилка HTTP! статус: ${response.status}`);
        }

        const data = await response.json();
        setGroups(data);
      } catch (e) {
        setError(e.message);
      } finally {
        setIsLoading(false);
      }
    };
    fetchGroups();
  }, []);

  const handleCheckboxChange = (group) => {
    setSelectedGroups((prev) =>
      prev.includes(group)
        ? prev.filter((g) => g !== group)
        : [...prev, group]
    );
  };

  const handleCheckboxChangeMarkets = (market) => {
    setSelectedMarkets((prev) =>
      prev.includes(market)
        ? prev.filter((m) => m !== market)
        : [...prev, market]
    );
  };

  const handleSubmit = async () => {
    setError(null);

    if (selectedGroups.length === 0) {
      setError('Виберіть хоча б одну групу.');
      return;
    }

    if (selectedMarkets.length === 0) {
      setError('Виберіть хоча б один магазин.');
      return;
    }

    if (!validateInputs(startDate, endDate, days_of_order, setError, todayStocsMode, 1)) {
      return;
    }

    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/auto_order_markets`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/zip',
        },
        body: JSON.stringify({
          groups: selectedGroups,
          markets: selectedMarkets,
          date_start: startDate,
          date_finish: endDate,
          days_of_order: parseInt(days_of_order),
          today_stocs_mode: todayStocsMode,
        }),
      });

      if (!response.ok) {
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          const errorData = await response.json();
          throw new Error(errorData.detail || `Помилка HTTP! статус: ${response.status}`);
        } else {
          const errorText = await response.text();
          console.error(errorText);
          throw new Error(`Несподівана помилка! Статус: ${response.status}`);
        }
      }

      const blob = await response.blob();
      console.log('Розмір Blob:', blob.size);
      console.log('Тип Blob:', blob.type);
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/zip')) {
        throw new Error('Непередбачений формат відповіді. Очікувався ZIP-файл.');
      }

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      if (!a) {
        throw new Error('Не вдалося створити елемент посилання.');
      }
      a.href = url;
      a.download = 'autoOrderMarkets.zip';
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
    <Paper elevation={3} sx={{ // Paper as main background/container
      width: '100%',
      minHeight: 'calc(100vh - 40px)', // Use minHeight instead of maxHeight for overall flexibility
      display: 'flex', // Flex container for its content
      flexDirection: 'column', // Stack children vertically
      margin: '0', // No auto margin
      backgroundColor: 'transparent', // Transparent background, mainContent provides the dark bg
      p: 3, // Internal padding for the entire form content
      boxSizing: 'border-box', // Include padding in element's total width and height
    }}>
      <Grid container spacing={3} sx={{ height: '100%' }}> {/* Main Grid container */}
        {/* Row 1: Date Form (centered) */}
        <Grid item xs={12}>
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="h5" gutterBottom color="white">
              Автозамовлення магазини
            </Typography>
            {error && (
              <Typography color="error" sx={{ mb: 2 }}>
                {error}
              </Typography>
            )}
            {isLoading && <Typography>Завантаження...</Typography>}
            <DateInputForm
              startDate={startDate} setStartDate={setStartDate}
              endDate={endDate} setEndDate={setEndDate}
              orderDays={days_of_order} setOrderDays={setOrderDays}
              handleDownload={handleSubmit} isLoading={isLoading} error={error}
              showTodayStocsModeCheckbox={true} todayStocsMode={todayStocsMode} setTodayStocsMode={setTodayStocsMode}
              sx={{ // Added sx prop to DateInputForm for styling flex items within its box
                  display: 'inline-block', // To center the form horizontally
              }}
            />
          </Box>
        </Grid>

        {/* Row 2: Groups and Markets (half width each, remaining height) */}
        <Grid item xs={12} sx={{ flexGrow: 1, display: 'flex' }}> {/* flexGrow 1 to take remaining height */}
          <Grid container spacing={3} sx={{ height: '100%' }}> {/* Inner Grid for Groups and Markets */}
            {/* Groups */}
            <Grid item xs={6} sx={{ display: 'flex', flexDirection: 'column' }}> {/* flex column for internal content */}
              <FormControl component="fieldset" sx={{ flexGrow: 1, minWidth: '250px', p: 1, border: '1px solid #ccc', borderRadius: '5px', backgroundColor: '#f5f5f5' }}>
                <FormLabel component="legend" sx={{ color: 'blue', mb: 3 }}>Групи товарів</FormLabel> {/* Changed color to black for visibility */}
                {groups.length > 0 ? (
                  <FormGroup sx={{ flexGrow: 1, overflowY: 'auto' }}> {/* flexGrow 1 for content to take height */}
                    {groups.map((group) => (
                      <FormControlLabel
                        key={group}
                        control={
                          <Checkbox
                            checked={selectedGroups.includes(group)}
                            onChange={() => handleCheckboxChange(group)}
                            value={group}
                            sx={{ color: 'grey.700' }}
                          />
                        }
                        label={group}
                        sx={{ color: 'black' }}
                      />
                    ))}
                  </FormGroup>
                ) : (
                  !isLoading && <Typography sx={{ color: 'black' }}>Групи відсутні</Typography>
                )}
              </FormControl>
            </Grid>

            {/* Markets */}
            <Grid item xs={6} sx={{ display: 'flex', flexDirection: 'column' }}> {/* flex column for internal content */}
              <FormControl component="fieldset" sx={{ flexGrow: 1, minWidth: '250px', p: 1, border: '1px solid #ccc', borderRadius: '5px', backgroundColor: '#f5f5f5' }}>
                <FormLabel component="legend" sx={{ color: 'blue', mb: 3 }}>Магазини</FormLabel> {/* Changed color to black for visibility */}
                {markets.length > 0 ? (
                  <FormGroup sx={{ flexGrow: 1, overflowY: 'auto' }}> {/* flexGrow 1 for content to take height */}
                    {markets.map((marketName) => (
                      <FormControlLabel
                        key={marketName}
                        control={
                          <Checkbox
                            checked={selectedMarkets.includes(marketName)}
                            onChange={() => handleCheckboxChangeMarkets(marketName)}
                            value={marketName}
                            sx={{ color: 'grey.700' }}
                          />
                        }
                        label={marketName}
                        sx={{ color: 'black' }}
                      />
                    ))}
                  </FormGroup>
                ) : (
                  !isLoading && <Typography sx={{ color: 'black' }}>Магазини відсутні</Typography>
                )}
              </FormControl>
            </Grid>
          </Grid>
        </Grid>
      </Grid>
    </Paper>
  );
};

export default AnalysisForm;