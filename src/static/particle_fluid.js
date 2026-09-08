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

    let currentScroll = window.scrollY || 0;
    let targetScroll = window.scrollY || 0;
    
    window.addEventListener('scroll', () => {
        targetScroll = window.scrollY;
    }, { passive: true });

    const uniforms = {
      u_time: { value: 0.0 },
      u_resolution: { value: new THREE.Vector2(window.innerWidth, window.innerHeight) },
      u_isDark: { value: document.documentElement.classList.contains('dark') ? 1.0 : 0.0 },
      u_texture: { value: bgTexture },
      u_imageAspect: { value: imageAspect },
      u_scrollY: { value: 0.0 }
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
        // Dark mode: keep it saturated, deepen shadows, cool tint
        vec3 colorDark = color * vec3(0.5, 0.6, 0.85);
        colorDark -= 0.05;
        colorDark = max(colorDark, 0.0);
        
        // Light mode: bright but slightly washed
        vec3 colorLight = color * 1.05;
        colorLight += 0.05;
        
        vec3 finalColor = mix(colorLight, colorDark, u_isDark);
        
        gl_FragColor = vec4(finalColor, 1.0);
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

    function animate() {
      requestAnimationFrame(animate);
      if (!reduceMotion) {
        uniforms.u_time.value = clock.getElapsedTime();
      }
      
      currentScroll += (targetScroll - currentScroll) * 0.1;
      uniforms.u_scrollY.value = currentScroll;
      
      const isDark = document.documentElement.classList.contains('dark');
      uniforms.u_isDark.value += ((isDark ? 1.0 : 0.0) - uniforms.u_isDark.value) * 0.05;

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
