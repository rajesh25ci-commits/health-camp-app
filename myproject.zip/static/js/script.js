/**
 * Smart Community Health Camp Management System - Core Client Script
 */

document.addEventListener('DOMContentLoaded', () => {
    // Auto-dismiss alert alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 5000);
    });

    console.log('Smart Community Health Camp System initialized.');
});
