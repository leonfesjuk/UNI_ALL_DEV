import React from 'react';
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import './index.css';
import AutoOrderMarkets from './components/autoorderm/AutoOrderMarkets.jsx';
import AutoOrderWarhause from './components/autoorderw/AutoOrderWarhause.jsx';
import OutProducts from './components/outProducts/OutProd.jsx';
import InsuranceBalance from './components/insurance/InsuranceBalance.jsx';
import Deshboard from './components/deshboard/Deshboard.jsx';
import SalesLooses from './components/salesLooses/SalesLooses.jsx';
import Menu from './components/menu/Menu.jsx';
import { Container } from '@mui/material';
import RedistributionPage from './components/redistribution/RedistributionPage';


const App = () => {
  return (
    <Router>
      {/* Статичне меню */}
      <Menu />

      {/* Динамічний контент */}
      <Container
      sx={{
        padding: '15px',
        overflow: 'auto',
        height: 'calc(100vh - 30px)', // Висота з урахуванням відступів
        margin: '15px', // Відступ від краю сторінки з усіх сторін
      }}>
        <Routes>
          <Route path="/" element={<AutoOrderWarhause />} />
          <Route path="/markets" element={<AutoOrderMarkets />} />
          <Route path="/deshboard" element={<Deshboard />} />
          <Route path="/out_products" element={<OutProducts />} />
          <Route path="/sales_looses" element={<SalesLooses />} />
          <Route path="/insurance_balance" element = {<InsuranceBalance />} />
          <Route path="/redistribution" element={<RedistributionPage />} />
        </Routes>
      </Container>
    </Router>
  );
};

export default App;