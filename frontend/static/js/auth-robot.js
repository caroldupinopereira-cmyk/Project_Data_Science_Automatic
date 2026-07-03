(function () {
    'use strict';

    var canvas = document.getElementById('robotCanvas');
    if (!canvas || typeof THREE === 'undefined' || typeof THREE.GLTFLoader === 'undefined') return;

    var scene, camera, renderer, clock;
    var robot = null;
    var eyes = [];
    var hands = [];
    var handOrigins = [];
    var particles = null;
    var glowLight = null;
    var glowRing = null;

    var nextBlink = 3;
    var blinkPhase = 0;
    var blinking = false;

    var nextWave = 4;
    var wavePhase = 0;
    var waving = false;

    function init() {
        clock = new THREE.Clock();
        scene = new THREE.Scene();
        camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
        camera.position.set(0, 0.5, 7);
        camera.lookAt(0, -0.2, 0);

        renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setClearColor(0x000000, 0);

        resize();
        window.addEventListener('resize', resize);

        var ambient = new THREE.AmbientLight(0xffffff, 0.5);
        scene.add(ambient);

        var dir = new THREE.DirectionalLight(0xffffff, 0.8);
        dir.position.set(3, 5, 4);
        scene.add(dir);

        var p1 = new THREE.PointLight(0x7c3aed, 1.8, 15);
        p1.position.set(-2, 2, 3);
        scene.add(p1);

        var p2 = new THREE.PointLight(0x2563eb, 1.2, 12);
        p2.position.set(2, -1, 2);
        scene.add(p2);

        var p3 = new THREE.PointLight(0x06b6d4, 0.6, 10);
        p3.position.set(0, 3, -2);
        scene.add(p3);

        loadRobot();
        initParticles();
        initGlow();
        animate();
    }

    function resize() {
        var parent = canvas.parentElement;
        if (!parent) return;
        var w = parent.clientWidth;
        var h = parent.clientHeight;
        if (!w || !h) return;
        canvas.width = w;
        canvas.height = h;
        canvas.style.cssText = 'width:' + w + 'px;height:' + h + 'px';
        if (camera) { camera.aspect = w / h; camera.updateProjectionMatrix(); }
        if (renderer) renderer.setSize(w, h);
    }

    function loadRobot() {
        var loader = new THREE.GLTFLoader();
        loader.load('/static/assets/robot.glb', function (gltf) {
            robot = gltf.scene.clone();
            robot.scale.set(2, 2, 2);
            robot.position.set(0, -0.3, 0);
            robot.rotation.y = -0.15;

            robot.traverse(function (c) {
                if (!c.isMesh) return;
                c.castShadow = c.receiveShadow = true;
                var n = c.name.toLowerCase();
                if (/eye/.test(n)) {
                    eyes.push(c);
                    console.log('[robot] eye found:', c.name, c);
                }
                if (/hand/.test(n)) {
                    hands.push(c);
                    handOrigins.push({ x: c.position.x, y: c.position.y, z: c.position.z });
                    console.log('[robot] hand found:', c.name, c);
                }
            });

            console.log('[robot] total eyes:', eyes.length, 'hands:', hands.length);

            scene.add(robot);
        }, undefined, function (err) { console.warn('[robot] load error:', err); });
    }

    function ease(t) { return -(Math.cos(Math.PI * t) - 1) / 2; }

    function initParticles() {
        var count = 120;
        var geo = new THREE.BufferGeometry();
        var pos = new Float32Array(count * 3);
        var cols = new Float32Array(count * 3);
        var pals = [
            [0.7, 0.3, 1.0],
            [0.4, 0.3, 1.0],
            [0.2, 0.8, 1.0],
            [1.0, 0.5, 0.8],
            [1.0, 1.0, 1.0],
        ];
        for (var i = 0; i < count; i++) {
            var theta = Math.random() * Math.PI * 2;
            var phi = Math.acos(2 * Math.random() - 1);
            var r = 0.6 + Math.random() * 1.4;
            pos[i * 3] = Math.sin(phi) * Math.cos(theta) * r;
            pos[i * 3 + 1] = Math.sin(phi) * Math.sin(theta) * r + 0.3;
            pos[i * 3 + 2] = Math.cos(phi) * r;
            var c = pals[Math.floor(Math.random() * pals.length)];
            cols[i * 3] = c[0];
            cols[i * 3 + 1] = c[1];
            cols[i * 3 + 2] = c[2];
        }
        geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
        geo.setAttribute('color', new THREE.BufferAttribute(cols, 3));

        var mat = new THREE.PointsMaterial({
            size: 0.06,
            transparent: true,
            opacity: 0.8,
            blending: THREE.AdditiveBlending,
            vertexColors: true,
            depthWrite: false,
            sizeAttenuation: true,
        });
        particles = new THREE.Points(geo, mat);
        scene.add(particles);
    }

    function initGlow() {
        glowLight = new THREE.PointLight(0x7c3aed, 1.2, 6);
        glowLight.position.set(0, -0.8, 0);
        scene.add(glowLight);

        var ringGeo = new THREE.RingGeometry(0.4, 0.9, 48);
        var ringMat = new THREE.MeshBasicMaterial({
            color: 0x7c3aed,
            transparent: true,
            opacity: 0.15,
            blending: THREE.AdditiveBlending,
            side: THREE.DoubleSide,
            depthWrite: false,
        });
        glowRing = new THREE.Mesh(ringGeo, ringMat);
        glowRing.position.set(0, -0.6, 0);
        glowRing.rotation.x = -Math.PI / 2;
        scene.add(glowRing);
    }

    function animate() {
        requestAnimationFrame(animate);
        var dt = clock.getDelta();
        var t = clock.getElapsedTime();

        if (robot) {
            robot.position.x = Math.sin(t * 0.45) * 0.2 + Math.sin(t * 1.0) * 0.06;
            robot.position.y = -0.3 + Math.sin(t * 1.2) * 0.03;
            robot.rotation.z = Math.sin(t * 0.5) * 0.03;
        }

        // Blink — scale + opacity for visibility
        if (eyes.length > 0) {
            if (!blinking) {
                nextBlink -= dt;
                if (nextBlink <= 0) { blinking = true; blinkPhase = 0; }
            }
            if (blinking) {
                blinkPhase += dt * 10;
                var s;
                if (blinkPhase < 0.5) s = 1 - ease(blinkPhase * 2);
                else s = ease((blinkPhase - 0.5) * 2);
                s = Math.max(0.01, s);
                for (var i = 0; i < eyes.length; i++) {
                    eyes[i].scale.y = s;
                    var mat = eyes[i].material;
                    if (mat) {
                        if (!mat.transparent) mat.transparent = true;
                        mat.opacity = s;
                        mat.needsUpdate = true;
                    }
                }
                if (blinkPhase >= 1) {
                    blinking = false;
                    nextBlink = 2.5 + Math.random() * 4;
                    for (var j = 0; j < eyes.length; j++) {
                        eyes[j].scale.y = 1;
                        var mat2 = eyes[j].material;
                        if (mat2) {
                            mat2.opacity = 1;
                            mat2.needsUpdate = true;
                        }
                    }
                }
            }
        }

        // Wave
        if (hands.length > 0) {
            if (!waving) {
                nextWave -= dt;
                if (nextWave <= 0) { waving = true; wavePhase = 0; }
            }
            if (waving) {
                wavePhase += dt * 1.4;
                var wp = Math.min(wavePhase, 1);
                var lift;
                if (wp < 0.3) lift = ease(wp / 0.3);
                else if (wp < 0.75) lift = 1 + Math.sin(((wp - 0.3) / 0.45) * Math.PI * 3) * 0.35;
                else lift = ease(1 - (wp - 0.75) / 0.25) * 0.5;

                for (var k = 0; k < hands.length; k++) {
                    hands[k].position.y = handOrigins[k].y + lift * 0.35;
                    hands[k].rotation.z = Math.sin(wp * Math.PI * 3.5) * 0.45 * Math.min(1, lift * 3);
                }

                if (wavePhase >= 1) {
                    waving = false;
                    nextWave = 3.5 + Math.random() * 4;
                    for (var m = 0; m < hands.length; m++) {
                        hands[m].position.y = handOrigins[m].y;
                        hands[m].rotation.z = 0;
                    }
                }
            }
        }

        // Glow under robot
        if (glowLight && robot) {
            var glowHue = Math.sin(t * 0.3) * 0.3 + 0.5;
            glowLight.intensity = 1.0 + Math.sin(t * 0.5) * 0.4;
            glowLight.color.setHSL(0.75 + Math.sin(t * 0.2) * 0.08, 0.8, 0.5);
            glowLight.position.x = robot.position.x;
        }
        if (glowRing && robot) {
            glowRing.position.x = robot.position.x;
            glowRing.scale.setScalar(1 + Math.sin(t * 0.4) * 0.1);
            glowRing.material.opacity = 0.12 + Math.sin(t * 0.5) * 0.06;
            glowRing.material.color.setHSL(0.75 + Math.sin(t * 0.2) * 0.08, 0.8, 0.5);
        }

        // Particles
        if (particles) {
            var pp = particles.geometry.attributes.position.array;
            for (var i = 0; i < pp.length; i += 3) {
                pp[i] += Math.sin(t * 0.5 + i * 0.3) * 0.001;
                pp[i + 1] += Math.cos(t * 0.35 + i * 0.2) * 0.0008;
                pp[i + 2] += Math.sin(t * 0.6 + i * 0.15) * 0.0007;
            }
            particles.geometry.attributes.position.needsUpdate = true;
            particles.rotation.y += 0.001;
            particles.material.opacity = 0.6 + Math.sin(t * 0.8) * 0.2;
            particles.material.size = 0.05 + Math.sin(t * 0.5) * 0.015;
        }

        renderer.render(scene, camera);
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
