import React, { useState } from "react";
import { useNavigate } from 'react-router-dom';
import { Button, Drawer, List, ListItem, ListItemText, IconButton } from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import WarehouseOutlinedIcon from '@mui/icons-material/WarehouseOutlined';
import StorefrontOutlinedIcon from '@mui/icons-material/StorefrontOutlined';
import BarChartOutlinedIcon from '@mui/icons-material/BarChartOutlined';
import ProductionQuantityLimitsIcon from '@mui/icons-material/ProductionQuantityLimits';
import GridGoldenratioIcon from '@mui/icons-material/GridGoldenratio';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import SwapHorizIcon from '@mui/icons-material/SwapHoriz';


function Menu() {
    const navigate = useNavigate();
    const [drawerOpen, setDrawerOpen] = useState(false);

    const toggleDrawer = (open) => (event) => {
        if (event.type === 'keydown' && (event.key === 'Tab' || event.key === 'Shift')) {
            return;
        }
        setDrawerOpen(open);
    };

    const menuItems = [
        { text: 'АЗ склад', path: '/', icon: <WarehouseOutlinedIcon /> },
        { text: 'АЗ магазини', path: '/markets', icon: <StorefrontOutlinedIcon /> },
        { text: 'Дешборд', path: '/deshboard', icon: <BarChartOutlinedIcon /> },
        { text: 'Виведення SKU', path: '/out_products', icon: <ProductionQuantityLimitsIcon /> },
        { text: 'Втрати продажів', path: '/sales_looses', icon: <TrendingDownIcon /> },
        { text: 'Страхові залишки', path: '/insurance_balance', icon: <GridGoldenratioIcon /> },
        { text: 'Перерозподіл', path: '/redistribution', icon: <SwapHorizIcon /> }
    ];

    return (
        <div>
            <IconButton 
                edge="start" 
                color="inherit" 
                aria-label="menu" 
                onClick={toggleDrawer(true)}
                sx={{ marginLeft: '15px', fontSize: '2rem', color: 'white' }} 
            >
                <MenuIcon fontSize="inherit" />
            </IconButton>
            <Drawer 
                anchor="left" 
                open={drawerOpen} 
                onClose={toggleDrawer(false)}
                sx={{ 
                    '& .MuiDrawer-paper': { 
                        backgroundColor: '#1e1e1e',
                    width: '150px'} }} // Змінюємо фон меню
            >
                <List>
                    {menuItems.map((item, index) => (
                        <Button 
                            key={index} 
                            onClick={() => { navigate(item.path); setDrawerOpen(false); }}
                            sx={{ 
                                textTransform: 'none', 
                                color: 'white', 
                                justifyContent: 'flex-start', 
                                width: '100%', 
                                padding: '10px 16px',
                                '&:hover': {
                                    backgroundColor: '#333', // Змінюємо колір фону при наведенні
                                    color: '#fff' // Змінюємо колір тексту при наведенні
                                }
                            }}
                            startIcon={item.icon}
                        >
                            {item.text}
                        </Button>
                    ))}
                </List>
            </Drawer>
        </div>
    );
}

export default Menu;