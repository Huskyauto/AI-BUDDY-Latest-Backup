/**
 * Global Scroll Position Manager 
 * 
 * This module provides site-wide scroll position management with
 * ALL auto-scrolling completely disabled throughout the application,
 * including after CBT coaching and any other page transitions.
 * 
 * Version: 1.3.0
 * Date: April 4, 2025
 * Changes: Completely disabled ALL automatic scroll restoration everywhere
 */

(function() {
    // Store the last user scroll position
    let lastUserScrollPosition = 0;
    
    // Initialize scroll position tracking without auto-restoration
    function initScrollManager() {
        console.log('Initializing global scroll position manager - Auto-scrolling disabled globally');
        
        // Store scroll position when user manually scrolls (for analytics only)
        let userScrollTimeout;
        window.addEventListener('scroll', function() {
            clearTimeout(userScrollTimeout);
            userScrollTimeout = setTimeout(() => {
                lastUserScrollPosition = window.scrollY || document.documentElement.scrollTop;
                console.log('User scrolled to position:', lastUserScrollPosition);
                // Still store for analytics but don't use for restoration
                sessionStorage.setItem('lastScrollPosition', lastUserScrollPosition);
            }, 150);
        });
        
        // Override browser's automatic scroll restoration behavior
        if ('scrollRestoration' in history) {
            history.scrollRestoration = 'manual'; // Still use manual to prevent browser auto-scroll
        }
        
        // AJAX request monitoring - disable auto-scrolling except for chat
        setupAjaxInterceptor();
        
        // Link click monitoring - disabled scroll restoration
        setupLinkInterceptor();
        
        // DO NOT restore position after page loads - intentionally disabled
        // Only clear flags from session storage
        clearScrollPositionFlags();
    }
    
    // Function to clear scroll position flags from session storage
    function clearScrollPositionFlags() {
        sessionStorage.removeItem('fromInternalNavigation');
        // Don't remove lastScrollPosition as it may be needed for analytics
    }
    
    // Setup AJAX request interceptor to maintain scroll position
    // ONLY for the chat window - all other auto-scrolling is disabled
    function setupAjaxInterceptor() {
        const originalOpen = XMLHttpRequest.prototype.open;
        
        XMLHttpRequest.prototype.open = function() {
            // Check if this is a chat-related endpoint that SHOULD auto-scroll
            const isChatEndpoint = arguments[1].includes('/chat') || 
                                  arguments[1].includes('/history');
            
            // Background refresh endpoints that would previously auto-scroll
            const isBackgroundRefresh = arguments[1].includes('/api/ring-data') || 
                                       arguments[1].includes('/api/ultrahuman-data');
            
            // Store current scroll position for analytics only
            const currentScroll = window.scrollY || document.documentElement.scrollTop;
            if (currentScroll > 0) {
                lastUserScrollPosition = currentScroll;
                sessionStorage.setItem('lastScrollPosition', lastUserScrollPosition);
                
                if (isBackgroundRefresh) {
                    console.log('Background refresh - scroll position at', currentScroll);
                }
            }
            
            // Only add auto-scroll for chat endpoints, NOT for any other pages
            if (isChatEndpoint) {
                this.addEventListener('load', function() {
                    // For chat endpoints, we'll let the chat.js handle scrolling
                    // This is just a stub to allow chat-specific auto-scrolling
                    console.log('Chat endpoint detected - allowing chat-specific auto-scroll behavior');
                });
            }
            
            return originalOpen.apply(this, arguments);
        };
    }
    
    // Setup link interceptor to store scroll position before navigation
    function setupLinkInterceptor() {
        document.addEventListener('click', function(e) {
            // Check if the clicked element is a link or has a link parent
            let target = e.target;
            let foundLink = false;
            
            // Check if it's a dropdown menu item (special handling for dropdowns)
            let isDropdownItem = false;
            let elem = e.target;
            while (elem && elem !== document) {
                if (elem.classList && (
                    elem.classList.contains('dropdown-item') || 
                    elem.classList.contains('dropdown-toggle') ||
                    elem.classList.contains('dropdown-clickable'))) {
                    isDropdownItem = true;
                    break;
                }
                elem = elem.parentNode;
            }
            
            // Skip our scroll position handling for dropdown menus
            if (isDropdownItem) {
                console.log('Dropdown interaction detected - not interfering with dropdown functionality');
                return;
            }
            
            // Continue with normal link handling
            while (target && target !== document && target.nodeName.toLowerCase() !== 'a') {
                target = target.parentNode;
            }
            
            if (target && target.nodeName.toLowerCase() === 'a') {
                // Check if it's a "no-auto-scroll" link that should be excluded
                if (target.classList.contains('no-auto-scroll')) {
                    console.log('Excluding no-auto-scroll link from scroll tracking');
                    return;
                }
                
                // Check if it's an internal link (same origin)
                const href = target.getAttribute('href');
                if (!href) return;
                
                const isInternalLink = !href.startsWith('http') || href.startsWith(window.location.origin);
                
                // Store current scroll position
                const currentScroll = window.scrollY || document.documentElement.scrollTop;
                if (currentScroll > 0 && isInternalLink) {
                    lastUserScrollPosition = currentScroll;
                    sessionStorage.setItem('lastScrollPosition', lastUserScrollPosition);
                    // Flag that we're navigating internally
                    sessionStorage.setItem('fromInternalNavigation', 'true');
                    console.log('Stored scroll position before internal navigation:', lastUserScrollPosition);
                }
            }
        }, false);
    }
    
    // Completely disabled auto-scroll restoration except for chat pages
    function restoreScrollPositionAfterLoad() {
        window.addEventListener('DOMContentLoaded', function() {
            // Check if we're on the chat page - ONLY restore auto-scroll for chat
            const isChatPage = window.location.pathname.includes('/chat') || 
                              document.getElementById('chat-container') !== null;
            
            // Get stored position from session storage (for analytics only)
            const storedPosition = sessionStorage.getItem('lastScrollPosition');
            const fromInternalNavigation = sessionStorage.getItem('fromInternalNavigation');
            
            if (storedPosition) {
                lastUserScrollPosition = parseInt(storedPosition, 10);
            }
            
            // Only attempt auto-scroll for chat pages
            if (isChatPage) {
                console.log('Chat page detected - allowing chat-specific scroll behavior');
                // Chat.js will handle the scrolling for the chat container
            } else {
                console.log('No scroll restoration - auto-scrolling disabled');
            }
            
            // Clear the navigation flag
            sessionStorage.removeItem('fromInternalNavigation');
        });
    }
    
    // Public API
    window.ScrollManager = {
        // Get the current user scroll position (for analytics only)
        getScrollPosition: function() {
            return lastUserScrollPosition;
        },
        
        // Manually preserve the current scroll position (for analytics only)
        saveScrollPosition: function() {
            lastUserScrollPosition = window.scrollY || document.documentElement.scrollTop;
            sessionStorage.setItem('lastScrollPosition', lastUserScrollPosition);
            console.log('Saved scroll position for analytics:', lastUserScrollPosition);
            return lastUserScrollPosition;
        },
        
        // Manually restore to the saved scroll position - ONLY for chat pages
        restoreScrollPosition: function() {
            // Only allow auto-scrolling for chat pages
            const isChatPage = window.location.pathname.includes('/chat') || 
                              document.getElementById('chat-container') !== null;
            
            if (!isChatPage) {
                console.log('Auto-scrolling disabled for non-chat pages');
                return;
            }
            
            if (lastUserScrollPosition > 0) {
                // Only perform scroll within a chat container if it exists
                const chatContainer = document.getElementById('chat-container');
                if (chatContainer) {
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                    console.log('Scrolled chat container to bottom');
                } else {
                    // Only for chat pages without a container element
                    window.scrollTo({
                        top: lastUserScrollPosition,
                        behavior: 'auto'
                    });
                    console.log('Chat page: Restored scroll position to:', lastUserScrollPosition);
                }
            }
        },
        
        // Helper method to scroll chat container to bottom (for chat.js)
        scrollChatToBottom: function() {
            const chatContainer = document.getElementById('chat-container');
            if (chatContainer) {
                chatContainer.scrollTop = chatContainer.scrollHeight;
                console.log('Scrolled chat container to bottom');
                return true;
            }
            return false;
        }
    };
    
    // Initialize on DOMContentLoaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initScrollManager);
    } else {
        initScrollManager();
    }
})();