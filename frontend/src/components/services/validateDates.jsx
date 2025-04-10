//Date format walidation
const validateInputs = (startDate, endDate, orderDays, setError, todayStocsMode = false, minOrderDays = null) => {
  const today = new Date(); // Сьогоднішня дата
  const yesterday = new Date(today); // Копіюємо сьогоднішню дату
  yesterday.setDate(today.getDate() - 1); // Вчорашня дата
  const yesterdayDate = yesterday.toISOString().split("T")[0]; // Форматуємо до "YYYY-MM-DD"
  console.log("Вчорашня дата:", yesterdayDate);
  console.log("Дата початку:", startDate);
  console.log("Дата кінця:", endDate);
    
    // If todayStocsMode is true, endDate can be today's date, but not in the future.
    // If todayStocsMode is false, endDate must be strictly before today's date.
    if (todayStocsMode) {
      const todayDate = today.toISOString().split("T")[0];
      if (endDate > todayDate) {
        setError("Дата кінця аналізу не може бути в майбутньому.");
        return false;
      }
    } else {
      // Original logic: endDate cannot be greater than yesterday's date
      if (endDate > yesterdayDate) {
        setError("Дата кінця аналізу не може бути більшою за вчорашню дату.");
        return false;
      }
    }
    if (startDate > endDate) {
      setError("Дата початку не може бути більшою за дату кінця.");
      return false;
    }
    if (!startDate || !endDate) {
      setError("Будь ласка, вкажіть дату початку та кінця аналізу.");
      return false;
    }
    if (minOrderDays !== null) { // Only apply this validation if a minimum is specified
        if (typeof orderDays !== "number" || orderDays < minOrderDays) {
            setError(`Кількість днів замовлення повинна бути числом не менше ${minOrderDays}.`);
            return false;
        }
    }
    return true;
  };

  export default validateInputs; 