// AI-BUDDY Service Worker for PWA support
// Updated Jan 2026 - Performance optimization with stale-while-revalidate
const CACHE_NAME = 'ai-buddy-cache-v3';
const STATIC_CACHE = 'ai-buddy-static-v3';
const DYNAMIC_CACHE = 'ai-buddy-dynamic-v1';

// Critical assets to precache (app shell)
const PRECACHE_URLS = [
  '/',
  '/static/css/custom.css',
  '/static/js/global_scroll_manager.js',
  '/static/js/timezone_handler.js',
  '/static/js/pwa-init.js',
  '/static/images/ai-buddy-logo.png',
  '/static/icons/icon.svg',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
  '/static/sounds/notification.mp3'
];

// Assets to cache with stale-while-revalidate strategy
const STALE_WHILE_REVALIDATE_URLS = [
  '/static/js/',
  '/static/css/',
  '/static/images/',
  '/static/icons/'
];

// URLs that should never be cached
const NEVER_CACHE_URLS = [
  '/self-care/wellness-check-in',
  '/self-care/api/wellness-check-in',
  '/api/',
  '/get-csrf-token',
  '/login',
  '/logout'
];

// Install event - cache essential files with parallel loading
self.addEventListener('install', event => {
  console.log('Service Worker: Installing...');
  event.waitUntil(
    Promise.all([
      caches.open(STATIC_CACHE).then(cache => {
        console.log('Service Worker: Precaching app shell');
        return cache.addAll(PRECACHE_URLS);
      }),
      caches.open(DYNAMIC_CACHE)
    ])
    .then(() => {
      console.log('Service Worker: Installation complete!');
      return self.skipWaiting();
    })
  );
});

// Activate event - cleanup old caches
self.addEventListener('activate', event => {
  console.log('Service Worker: Activating...');
  const validCaches = [STATIC_CACHE, DYNAMIC_CACHE, CACHE_NAME];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (!validCaches.includes(cacheName)) {
            console.log('Service Worker: Clearing old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
    .then(() => {
      console.log('Service Worker: Now active, claiming clients');
      return self.clients.claim();
    })
  );
});

// Fetch event - serve cached content or fetch from network
self.addEventListener('fetch', event => {
  // Handle cross-origin requests specifically for PWA mode
  if (!event.request.url.startsWith(self.location.origin)) {
    console.log('Service Worker: Cross-origin request in PWA mode:', event.request.url);
    // For cross-origin requests in PWA, we need to pass through with credentials
    // but handle SSL errors gracefully
    event.respondWith(
      fetch(event.request.clone(), {
        credentials: 'include', 
        mode: 'cors',
        // Ignore certificate errors in PWA mode to prevent SSL issues
        // This is a workaround for the SSL SYSCALL error: EOF detected issue
        referrerPolicy: 'no-referrer-when-downgrade'
      })
      .then(response => {
        console.log('Service Worker: Cross-origin request successful');
        return response;
      })
      .catch(error => {
        console.error('Service Worker: Cross-origin request failed:', error);
        // Check if this is an SSL error
        const isSSLError = error.message && 
          (error.message.includes('SSL') || 
           error.message.includes('certificate') ||
           error.message.includes('EOF detected'));
           
        if (isSSLError) {
          console.log('Service Worker: SSL error detected, attempting to use HTTP fallback');
          // Try again with HTTP if possible as a fallback
          // This is a last resort for development environments
          const httpUrl = event.request.url.replace('https://', 'http://');
          return fetch(new Request(httpUrl, {
            method: event.request.method,
            headers: event.request.headers,
            body: event.request.body,
            mode: 'cors',
            credentials: 'include'
          }))
          .catch(fallbackError => {
            console.error('Service Worker: HTTP fallback also failed:', fallbackError);
            return new Response(JSON.stringify({
              status: 'error',
              message: 'SSL error occurred and fallback also failed. Please try again in browser mode.'
            }), {
              headers: { 'Content-Type': 'application/json' }
            });
          });
        }
        
        return new Response(JSON.stringify({
          status: 'error',
          message: 'Network error while fetching cross-origin resource: ' + error.message
        }), {
          headers: { 'Content-Type': 'application/json' }
        });
      })
    );
    return;
  }
  
  // Skip never-cache URLs including form submissions
  for (const url of NEVER_CACHE_URLS) {
    if (event.request.url.includes(url)) {
      console.log('Service Worker: Bypassing cache for:', event.request.url);
      event.respondWith(fetch(event.request));
      return;
    }
  }
  
  // Handle POST requests (like form submissions) by passing through to the network
  if (event.request.method === 'POST') {
    console.log('Service Worker: POST request detected:', event.request.url);
    
    // Special handling for wellness check-in form submissions to avoid SSL errors
    if (event.request.url.includes('/wellness-check-in') || 
        event.request.url.includes('/self-care/api/')) {
      console.log('Service Worker: Wellness check-in form submission detected');
      
      event.respondWith(
        fetch(event.request.clone(), {
          credentials: 'include',
          mode: 'cors',
          referrerPolicy: 'no-referrer-when-downgrade',
          // Ensure cache is bypassed
          cache: 'no-store',
          redirect: 'follow'
        })
        .then(response => {
          console.log('Service Worker: Wellness check-in submission successful', response.status);
          return response;
        })
        .catch(error => {
          console.error('Service Worker: Wellness check-in submission failed:', error);
          
          // Check if this is an SSL error
          const isSSLError = error.message && 
            (error.message.includes('SSL') || 
             error.message.includes('certificate') ||
             error.message.includes('EOF detected'));
             
          if (isSSLError) {
            console.log('Service Worker: SSL error in wellness check-in, notifying client');
            // Signal to the client that there was an SSL error
            clients.matchAll().then(clientList => {
              clientList.forEach(client => {
                client.postMessage({
                  type: 'WELLNESS_CHECKIN_SSL_ERROR',
                  url: event.request.url,
                  error: error.message
                });
              });
            });
            
            return new Response(JSON.stringify({
              status: 'error',
              message: 'SSL error detected. Please try again or use browser mode.',
              error_type: 'ssl_error'
            }), {
              headers: { 'Content-Type': 'application/json' },
              status: 499 // Custom status code for client to detect
            });
          }
          
          return new Response(JSON.stringify({
            status: 'error',
            message: 'Network error during form submission: ' + error.message
          }), {
            headers: { 'Content-Type': 'application/json' },
            status: 500
          });
        })
      );
      return;
    }
    
    // Default handling for other POST requests
    console.log('Service Worker: Standard POST request, passing through to network');
    event.respondWith(fetch(event.request));
    return;
  }
  
  // Check if this is a static asset for stale-while-revalidate
  const isStaticAsset = STALE_WHILE_REVALIDATE_URLS.some(url => event.request.url.includes(url));
  
  if (isStaticAsset) {
    // Stale-while-revalidate: return cached immediately, update in background
    event.respondWith(
      caches.open(STATIC_CACHE).then(cache => {
        return cache.match(event.request).then(cachedResponse => {
          const fetchPromise = fetch(event.request).then(networkResponse => {
            if (networkResponse && networkResponse.status === 200) {
              cache.put(event.request, networkResponse.clone());
            }
            return networkResponse;
          }).catch(() => cachedResponse);
          
          // Return cached version immediately, update in background
          return cachedResponse || fetchPromise;
        });
      })
    );
    return;
  }
  
  // Handle other GET requests with network-first, cache fallback
  event.respondWith(
    fetch(event.request)
      .then(response => {
        if (!response || response.status !== 200) {
          return response;
        }
        
        // Cache successful responses
        const responseToCache = response.clone();
        caches.open(DYNAMIC_CACHE).then(cache => {
          if (!event.request.url.includes('/api/') && 
              !NEVER_CACHE_URLS.some(url => event.request.url.includes(url))) {
            cache.put(event.request, responseToCache);
          }
        });
        
        return response;
      })
      .catch(() => {
        // Network failed, try cache
        return caches.match(event.request).then(cachedResponse => {
          if (cachedResponse) {
            console.log('Service Worker: Serving from cache:', event.request.url);
            return cachedResponse;
          }
          // Return offline page or empty response
          return new Response('Offline', { status: 503, statusText: 'Offline' });
        });
      })
  );
});

// Handle background sync for offline functionality
self.addEventListener('sync', event => {
  console.log('Service Worker: Sync event received', event.tag);
  if (event.tag === 'sync-wellness-checkin') {
    event.waitUntil(syncWellnessCheckin());
  }
});

// Function to sync wellness check-ins that were made offline
function syncWellnessCheckin() {
  console.log('Service Worker: Attempting to sync wellness check-in data');
  return self.clients.matchAll().then(clients => {
    clients.forEach(client => {
      client.postMessage({
        type: 'SYNC_WELLNESS_CHECKIN'
      });
    });
  });
}

// Push notification handler
self.addEventListener('push', event => {
  console.log('Service Worker: Push notification received');
  if (event.data) {
    const data = event.data.json();
    const title = data.title || 'AI-BUDDY Reminder';
    const options = {
      body: data.body || 'Time for your wellness check-in!',
      icon: '/static/icons/icon-192x192.png',
      badge: '/static/icons/checkin-192x192.png',
      vibrate: [100, 50, 100], // Vibration pattern
      data: {
        url: data.url || '/'
      }
    };
    
    event.waitUntil(
      self.registration.showNotification(title, options)
    );
  }
});

// Notification click handler
self.addEventListener('notificationclick', event => {
  console.log('Service Worker: Notification click received');
  event.notification.close();
  
  // Use the custom URL from the notification if available
  const urlToOpen = event.notification.data && event.notification.data.url ? 
                    event.notification.data.url : '/';
  
  // This looks to see if the current is already open and focuses if it is
  event.waitUntil(
    clients.matchAll({
      type: "window"
    })
    .then(clientList => {
      for (const client of clientList) {
        if (client.url === urlToOpen && 'focus' in client)
          return client.focus();
      }
      if (clients.openWindow)
        return clients.openWindow(urlToOpen);
    })
  );
});