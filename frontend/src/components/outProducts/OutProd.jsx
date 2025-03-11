import React from "react";
import OutProductsStart from "./utils/DateChoose.jsx";
import ArchiveProductsStart from "./utils/ArciveProduct.jsx";
import MarketDownProducts from "./utils/MarketDownProducts.jsx";
import PricesWithStocks from "./utils/PricesWithStocks.jsx";


function OutProducts() {
    return (
        <div className="content">
            <h3>Вивантаження товарів, що вийшли</h3>
            <OutProductsStart />
            <hr />
            <h3>Вивантаження архівних товарів</h3>
            <ArchiveProductsStart />
            <hr />
            <h3>Товари в уцінці</h3>
            <MarketDownProducts />
            <hr />
            <h3>Ціни на асортимент</h3>
            <PricesWithStocks />
        </div>
    );
}
    
export default OutProducts;