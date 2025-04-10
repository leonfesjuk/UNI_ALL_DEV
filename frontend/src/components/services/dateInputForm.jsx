import React from 'react';
import { Button, CircularProgress, Typography, Box, Alert } from '@mui/material';

const DateInputForm = ({
  startDate,
  setStartDate,
  endDate,
  setEndDate,
  orderDays,
  setOrderDays,
  handleDownload,
  isLoading,
  error,
  showTodayStocsModeCheckbox = false,
  todayStocsMode,
  setTodayStocsMode,
}) => {
  return (
    <Box
      sx={{
        padding: '15px',
        border: '1px solid #ccc',
        borderRadius: '5px',
        marginTop: '15px',
      }}
    >
      <Box
        className="date-container"
        sx={{ display: 'flex', flexDirection: 'row', flexWrap: 'wrap', gap: '15px', marginBottom: '15px' }}
      >
        <Box>
          <label className="date-label">Date start:</label>
          <input
            className="date-input"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
        </Box>

        <Box>
          <label className="date-label">Date finish:</label>
          <input
            className="date-input"
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
        </Box>

        {orderDays !== undefined && setOrderDays !== undefined && (
          <Box>
            <label className="date-label">Кількість днів замовлення:</label>
            <input
              className="date-input"
              type="number"
              value={orderDays}
              min="1"
              onChange={(e) => setOrderDays(Number(e.target.value))}
            />
          </Box>
        )}

        {showTodayStocsModeCheckbox && (
          <Box sx={{ display: 'flex', alignItems: 'center', mt: 2, gap: '8px' }}>
            <input
              type="checkbox"
              id="todayStocsMode"
              checked={todayStocsMode}
              onChange={(e) => setTodayStocsMode(e.target.checked)}
            />
            <label htmlFor="todayStocsMode" className="date-label">Залишки на сьогодні</label>
          </Box>
        )}
      </Box>

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
          {isLoading ? "Processing file" : "Start Auto Order"}
        </Button>
      </Box>

      {isLoading && (
        <Typography
          variant="body2"
          sx={{
            color: 'white',
            backgroundColor: 'purple',
            padding: '10px',
            borderRadius: '5px',
            marginTop: '10px',
          }}
        >
          Завантаження...
        </Typography>
      )}
      {error && (
        <Alert variant="outlined" severity="warning" sx={{ marginTop: '10px' }}>
          {error}
        </Alert>
      )}
    </Box>
  );
};

export default DateInputForm;