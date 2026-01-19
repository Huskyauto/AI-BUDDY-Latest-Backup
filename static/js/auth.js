document.addEventListener('DOMContentLoaded', function() {
    // Form validation for login and registration
    const loginForm = document.querySelector('form[action*="login"]');
    const registerForm = document.querySelector('form[action*="register"]');

    function validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }

    function validatePassword(password) {
        // Minimum 6 characters
        return password.length >= 6;
    }

    function validateUsername(username) {
        // Minimum 3 characters, alphanumeric and underscores
        const re = /^[a-zA-Z0-9_]{3,}$/;
        return re.test(username);
    }

    function showError(input, message) {
        const formGroup = input.closest('.mb-3');
        const existingError = formGroup.querySelector('.invalid-feedback');
        
        input.classList.add('is-invalid');
        
        if (!existingError) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'invalid-feedback';
            errorDiv.textContent = message;
            formGroup.appendChild(errorDiv);
        } else {
            existingError.textContent = message;
        }
    }

    function clearError(input) {
        const formGroup = input.closest('.mb-3');
        const existingError = formGroup.querySelector('.invalid-feedback');
        
        input.classList.remove('is-invalid');
        if (existingError) {
            existingError.remove();
        }
    }

    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            let isValid = true;
            const email = this.querySelector('#email');
            const password = this.querySelector('#password');

            // Clear previous errors
            clearError(email);
            clearError(password);

            // Validate email
            if (!validateEmail(email.value.trim())) {
                showError(email, 'Please enter a valid email address');
                isValid = false;
            }

            // Validate password
            if (!validatePassword(password.value)) {
                showError(password, 'Password must be at least 6 characters long');
                isValid = false;
            }

            if (!isValid) {
                e.preventDefault();
            }
        });
    }

    if (registerForm) {
        registerForm.addEventListener('submit', function(e) {
            let isValid = true;
            const username = this.querySelector('#username');
            const email = this.querySelector('#email');
            const password = this.querySelector('#password');

            // Clear previous errors
            clearError(username);
            clearError(email);
            clearError(password);

            // Validate username
            if (!validateUsername(username.value.trim())) {
                showError(username, 'Username must be at least 3 characters long and contain only letters, numbers, and underscores');
                isValid = false;
            }

            // Validate email
            if (!validateEmail(email.value.trim())) {
                showError(email, 'Please enter a valid email address');
                isValid = false;
            }

            // Validate password
            if (!validatePassword(password.value)) {
                showError(password, 'Password must be at least 6 characters long');
                isValid = false;
            }

            if (!isValid) {
                e.preventDefault();
            }
        });
    }

    // Add input event listeners for real-time validation
    document.querySelectorAll('input').forEach(input => {
        input.addEventListener('input', function() {
            clearError(this);
        });
    });

    // Show/hide password functionality
    const passwordInputs = document.querySelectorAll('input[type="password"]');
    passwordInputs.forEach(input => {
        const toggleBtn = document.createElement('button');
        toggleBtn.type = 'button';
        toggleBtn.className = 'btn btn-outline-secondary';
        toggleBtn.innerHTML = '<i class="bi bi-eye"></i>';
        toggleBtn.style.position = 'absolute';
        toggleBtn.style.right = '0';
        toggleBtn.style.zIndex = '10';
        
        input.parentElement.style.position = 'relative';
        input.parentElement.appendChild(toggleBtn);

        toggleBtn.addEventListener('click', function() {
            const type = input.getAttribute('type') === 'password' ? 'text' : 'password';
            input.setAttribute('type', type);
            this.innerHTML = type === 'password' ? '<i class="bi bi-eye"></i>' : '<i class="bi bi-eye-slash"></i>';
        });
    });
});
