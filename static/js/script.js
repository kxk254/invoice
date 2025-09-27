
    function formatWithCommas(input) {
        // Remove existing commas
        let value = input.value.replace(/,/g, '');
        // Only format if the value is a valid number
        if (!isNaN(value) && value.trim() !== "") {
            input.value = new Intl.NumberFormat('en-US').format(value);
        } else {
            input.value = value; // Retain invalid input for correction
        }
    }


