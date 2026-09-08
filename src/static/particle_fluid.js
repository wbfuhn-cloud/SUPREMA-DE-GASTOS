/**
 * =========================================================================
 *  AURORA BOREAL THREE.JS — GASTOS RACCOON
 *  Fondo animado de aurora boreal en la parte superior con cielo oscuro.
 * =========================================================================
 */

(function () {
  'use strict';

  if (window.__THREE_PARTICLE_FLUID_INIT__) return;
  window.__THREE_PARTICLE_FLUID_INIT__ = true;

  function initParticleFluid() {
    if (typeof THREE === 'undefined') {
      setTimeout(initParticleFluid, 50);
      return;
    }

    let canvas = document.getElementById('bg-particle-fluid');
    if (!canvas) {
      canvas = document.createElement('canvas');
      canvas.id = 'bg-particle-fluid';
      canvas.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;pointer-events:none;z-index:-1;display:block;';
      document.body.insertBefore(canvas, document.body.firstChild);
    }

    const scene = new THREE.Scene();
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 10);
    camera.position.z = 1;

    const renderer = new THREE.WebGLRenderer({
      canvas: canvas,
      alpha: true,
      antialias: true,
      powerPreference: 'high-performance',
      preserveDrawingBuffer: true
    });
    renderer.setSize(window.innerWidth, window.innerHeight);
    // RECTIFICA v2.7.0 Liquid Glass: en móvil baja resolución para 60fps
    var isMobile = window.innerWidth < 768;
    renderer.setPixelRatio(isMobile ? 1 : Math.min(window.devicePixelRatio || 1, 2));

    const textureLoader = new THREE.TextureLoader();
    let imageAspect = 16.0 / 9.0;
    const bgTexture = textureLoader.load('/static/bg_liquid.jpg', function(tex) {
      imageAspect = tex.image.width / tex.image.height;
      if (uniforms.u_imageAspect) uniforms.u_imageAspect.value = imageAspect;
    });
    bgTexture.minFilter = THREE.LinearFilter;
    bgTexture.magFilter = THREE.LinearFilter;
    bgTexture.wrapS = THREE.MirroredRepeatWrapping;
    bgTexture.wrapT = THREE.MirroredRepeatWrapping;

    let currentScroll = 0;
    let targetScroll = 0;
    
    window.addEventListener('scroll', (e) => {
        const target = e.target;
        const st = target.scrollTop || window.scrollY || 0;
        // Filtrar pequeños divs, solo reaccionar si es el documento o el contenedor principal
        if (target === document || (target.clientHeight && target.clientHeight > window.innerHeight * 0.5)) {
            targetScroll = st;
        }
    }, { passive: true, capture: true });

    const uniforms = {
      u_time: { value: 0.0 },
      u_resolution: { value: new THREE.Vector2(window.innerWidth, window.innerHeight) },
      u_isDark: { value: document.documentElement.classList.contains('dark') ? 1.0 : 0.0 },
      u_texture: { value: bgTexture },
      u_imageAspect: { value: imageAspect },
      u_scrollY: { value: 0.0 },
      u_themeTransition: { value: 1.0 }
    };

    const vertexShader = `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = vec4(position, 1.0);
      }
    `;

    const fragmentShader = `
      uniform float u_time;
      uniform vec2 u_resolution;
      uniform float u_isDark;
      uniform sampler2D u_texture;
      uniform float u_imageAspect;
      uniform float u_scrollY;
      uniform float u_themeTransition;
      varying vec2 vUv;

      vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
      vec2 mod289(vec2 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
      vec3 permute(vec3 x) { return mod289(((x*34.0)+1.0)*x); }

      float snoise(vec2 v) {
        const vec4 C = vec4(0.211324865405187, 0.366025403784439, -0.577350269189626, 0.024390243902439);
        vec2 i  = floor(v + dot(v, C.yy) );
        vec2 x0 = v -   i + dot(i, C.xx);
        vec2 i1;
        i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
        vec4 x12 = x0.xyxy + C.xxzz;
        x12.xy -= i1;
        i = mod289(i);
        vec3 p = permute( permute( i.y + vec3(0.0, i1.y, 1.0 )) + i.x + vec3(0.0, i1.x, 1.0 ));
        vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);
        m = m*m ;
        m = m*m ;
        vec3 x = 2.0 * fract(p * C.www) - 1.0;
        vec3 h = abs(x) - 0.5;
        vec3 ox = floor(x + 0.5);
        vec3 a0 = x - ox;
        m *= 1.79284291400159 - 0.85373472095314 * ( a0*a0 + h*h );
        vec3 g;
        g.x  = a0.x  * x0.x  + h.x  * x0.y;
        g.yz = a0.yz * x12.xz + h.yz * x12.yw;
        return 130.0 * dot(m, g);
      }

      void main() {
        float screenAspect = u_resolution.x / u_resolution.y;
        vec2 uv = gl_FragCoord.xy / u_resolution.xy;
        
        // Background-size: cover logic
        vec2 scale = vec2(1.0);
        if (screenAspect > u_imageAspect) {
            scale.y = screenAspect / u_imageAspect;
        } else {
            scale.x = u_imageAspect / screenAspect;
        }
        
        vec2 centeredUv = uv - 0.5;
        
        // Theme Transition Shockwave
        float pulse = sin(u_themeTransition * 3.14159);
        float distToCenter = length(centeredUv);
        float waveRadius = u_themeTransition * 1.5;
        float waveThickness = 0.2;
        // FIX: En WebGL 1, smoothstep falla si edge0 >= edge1
        float ring1 = smoothstep(waveRadius - waveThickness, waveRadius, distToCenter);
        float ring2 = 1.0 - smoothstep(waveRadius, waveRadius + waveThickness, distToCenter);
        float ring = ring1 * ring2;
                   
        if (pulse > 0.0) {
            vec2 outwardDir = normalize(centeredUv);
            centeredUv += outwardDir * ring * 0.15 * pulse;
        }
        
        // Scroll Parallax offset
        float scrollOffset = (u_scrollY / u_resolution.y) * 0.15; // 15% parallax strength
        centeredUv.y -= scrollOffset;
        
        centeredUv /= scale;
        
        float time = u_time * 0.15;
        
        // Fluid Ripple Distortion
        float noise = snoise(vec2(centeredUv.x * 3.0 + time, centeredUv.y * 3.0 - time)) * 0.015;
        float noise2 = snoise(vec2(centeredUv.x * 5.0 - time * 0.8, centeredUv.y * 5.0 + time * 1.2)) * 0.008;
        
        // Slow hypnotic zoom and pan
        float zoom = 1.08 + sin(time * 0.4) * 0.03;
        vec2 pan = vec2(cos(time * 0.2) * 0.01, sin(time * 0.3) * 0.01);
        
        vec2 finalUv = centeredUv * (1.0 / zoom) + 0.5 + pan + vec2(noise + noise2);
        
        vec4 texColor = texture2D(u_texture, finalUv);
        
        // Aumentar saturación y profundidad de los colores
        vec3 color = texColor.rgb;
        
        // Contraste para oscurecer los colores profundos
        color = smoothstep(0.0, 1.0, color);
        
        // Incrementar la saturación 1.5x
        float luminance = dot(color, vec3(0.299, 0.587, 0.114));
        color = mix(vec3(luminance), color, 1.5);
        
        // Dynamic adaptation to theme (Light vs Dark)
        // Night Mode: Distinct, flowing dark night waves (Indigo, Deep Cobalt, Royal Violet)
        vec2 uvNight = centeredUv * 1.8;
        float wave1 = snoise(vec2(uvNight.x * 2.5 + time * 0.25, uvNight.y * 1.5 - time * 0.20));
        float wave2 = snoise(vec2(uvNight.x * 4.0 - time * 0.35, uvNight.y * 3.0 + time * 0.30));
        float wave3 = snoise(vec2(uvNight.x * 1.2 + time * 0.15, uvNight.y * 2.5 + time * 0.10));
        
        // Layered organic dark wave contours
        float darkShape = smoothstep(-0.4, 0.6, wave1 + wave2 * 0.4 + wave3 * 0.3);
        float secondaryShape = smoothstep(-0.2, 0.8, wave2 - wave1 * 0.5);
        
        vec3 deepSpace = vec3(0.03, 0.05, 0.12);     // Fondo obsidiana noche
        vec3 cobaltNight = vec3(0.0, 0.30, 0.90);   // Ondas azul cobalto nocturno (#004CD9)
        vec3 violetNight = vec3(0.45, 0.10, 0.85);  // Ondas violeta nocturno (#731AD9)
        vec3 cyanGlow = vec3(0.0, 0.60, 0.90);     // Brillo en crestas de las ondas nocturnas
        
        vec3 colorDark = mix(deepSpace, cobaltNight, darkShape);
        colorDark = mix(colorDark, violetNight, secondaryShape * 0.75);
        colorDark += cyanGlow * pow(clamp(wave1 * wave2, 0.0, 1.0), 2.0) * 0.40; // Crestas luminosas
        
        // Light mode: bright, vibrant liquid fluid from bg_liquid.jpg texture
        vec3 colorLight = color * 1.05 + 0.05;
        
        // El nuevo tema entra como una ola de choque desde el centro
        float targetThemeWeight = 1.0 - smoothstep(waveRadius - 0.12, waveRadius + 0.12, distToCenter);
        float oldTheme = 1.0 - u_isDark;
        float currentPixelTheme = mix(oldTheme, u_isDark, targetThemeWeight);
        
        vec3 finalColor = mix(colorLight, colorDark, currentPixelTheme);
        float finalAlpha = mix(1.0, 0.88, currentPixelTheme);
        
        gl_FragColor = vec4(finalColor, finalAlpha);
      }
    `;

    const material = new THREE.ShaderMaterial({
      vertexShader: vertexShader,
      fragmentShader: fragmentShader,
      uniforms: uniforms
    });

    const geometry = new THREE.PlaneGeometry(2, 2);
    const mesh = new THREE.Mesh(geometry, material);
    scene.add(mesh);

    window.addEventListener('resize', () => {
      renderer.setSize(window.innerWidth, window.innerHeight);
      uniforms.u_resolution.value.set(window.innerWidth, window.innerHeight);
    });

    const clock = new THREE.Clock();
    // RECTIFICA v2.7.0: respeta prefers-reduced-motion (congela aurora)
    var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    let targetTheme = document.documentElement.classList.contains('dark') ? 1.0 : 0.0;
    let transitionTimer = 1.0;
    let isTransitioning = false;

    function animate() {
      requestAnimationFrame(animate);
      if (!reduceMotion) {
        uniforms.u_time.value = clock.getElapsedTime();
      }
      
      currentScroll += (targetScroll - currentScroll) * 0.1;
      uniforms.u_scrollY.value = currentScroll;
      
      const currentHTMLTheme = document.documentElement.classList.contains('dark') ? 1.0 : 0.0;
      if (currentHTMLTheme !== targetTheme) {
          targetTheme = currentHTMLTheme;
          isTransitioning = true;
          transitionTimer = 0.0;
      }
      
      if (isTransitioning) {
          transitionTimer += 0.02; // completa en ~50 frames (0.8s)
          if (transitionTimer >= 1.0) {
              transitionTimer = 1.0;
              isTransitioning = false;
              // Avisar a liquidGL que capture AHORA que el efecto termino
              if (window.liquidGL && window.liquidGL.syncWith) {
                  setTimeout(() => { window.liquidGL.syncWith(); }, 50);
              }
          }
      }
      
      uniforms.u_themeTransition.value = transitionTimer;
      uniforms.u_isDark.value = targetTheme;

      renderer.render(scene, camera);
    }

    animate();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initParticleFluid);
  } else {
    initParticleFluid();
  }
})();
