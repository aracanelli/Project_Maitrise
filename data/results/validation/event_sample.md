# Event extraction validation sample

Seed 11, up to 40 core events per label, at most 2 per commit. Annotate `event_sample.csv`:
`label_correct` (y/n), `is_logging_statement` (y/n), `level_correct` (y/n/na), `notes`.

## OpenKeeper:0cae22ea6956:0 — ADD_LOG

- repo: OpenKeeper  commit: https://github.com/tonihele/OpenKeeper/commit/0cae22ea6956cf48439ada3ebb387a41e4957fb7
- method: `ConvertFonts.internalExecuteTask()` in `src/toniarts/openkeeper/tools/convert/conversion/task/ConvertFonts.java`
- added statement (post-state): `LOGGER.log(Level.SEVERE, "Failed to wait font conversion complete!", ex)`
- levels: None -> ERROR

Pre-state:
```java
   58    @Override
   59        public void internalExecuteTask() {
   60            convertFonts(dungeonKeeperFolder, destination);
   61        }
```
Post-state:
```java
   77    @Override
   78        public void internalExecuteTask() {
   79            try {
   80                convertFonts(dungeonKeeperFolder, destination);
   81            } finally {
   82                executorService.shutdown();
   83                try {
   84                    executorService.awaitTermination(Long.MAX_VALUE, TimeUnit.DAYS);
   85                } catch (InterruptedException ex) {
   86 >>                 LOGGER.log(Level.SEVERE, "Failed to wait font conversion complete!", ex);
   87                }
   88            }
   89        }
```

## OpenKeeper:a92a3d959bd3:15 — ADD_LOG

- repo: OpenKeeper  commit: https://github.com/tonihele/OpenKeeper/commit/a92a3d959bd3340d203ee73c19bfcaca0f98e8e1
- method: `KwdFile.readKeeperSpells(KwdHeader,RandomAccessFile)` in `src/toniarts/openkeeper/tools/convert/map/KwdFile.java`
- added statement (post-state): `logger.warning("Overrides keeper spells!")`
- levels: None -> WARN

Pre-state:
```java
 2018    private void readKeeperSpells(KwdHeader header, RandomAccessFile file) throws IOException {
 2019    
 2020            // Read the keeper spells catalog
 2021            logger.info("Reading keeper spells!");
 2022            keeperSpells = new HashMap<>(header.getItemCount());
 2023            for (int i = 0; i < header.getItemCount(); i++) {
 2024                long offset = file.getFilePointer();
 2025                KeeperSpell keeperSpell = new KeeperSpell();
 2026                byte[] bytes = new byte[32];
 2027                file.read(bytes);
 2028                keeperSpell.setName(ConversionUtils.bytesToString(bytes).trim());
 2029                keeperSpell.setGuiIcon(readArtResource(file));
 2030                keeperSpell.setEditorIcon(readArtResource(file));
 2031                keeperSpell.setXc8(ConversionUtils.readInteger(file));
 2032                keeperSpell.setRechargeTime(ConversionUtils.readInteger(file) / ConversionUtils.FLOAT);
 2033                keeperSpell.setShotData1(ConversionUtils.readInteger(file));
 2034                keeperSpell.setShotData2(ConversionUtils.readInteger(file));
 2035                keeperSpell.setResearchTime(ConversionUtils.readUnsignedShort(file));
 2036                keeperSpell.setTargetRule(ConversionUtils.parseEnum((short) file.readUnsignedByte(), KeeperSpell.TargetRule.class));
 2037                keeperSpell.setOrderInEditor((short) file.readUnsignedByte());
 2038                keeperSpell.setFlags(ConversionUtils.parseFlagValue(ConversionUtils.readUnsignedInteger(file), KeeperSpell.KeeperSpellFlag.class));
      ...
```
Post-state:
```java
 1741    private void readKeeperSpells(KwdHeader header, RandomAccessFile file) throws IOException {
 1742    
 1743            // Read the keeper spells catalog
 1744            if (keeperSpells == null) {
 1745                logger.info("Reading keeper spells!");
 1746                keeperSpells = new HashMap<>(header.getItemCount());
 1747            } else {
 1748 >>             logger.warning("Overrides keeper spells!");
 1749            }
 1750            
 1751            for (int i = 0; i < header.getItemCount(); i++) {
 1752                long offset = file.getFilePointer();
 1753                KeeperSpell keeperSpell = new KeeperSpell();
 1754                byte[] bytes = new byte[32];
 1755                file.read(bytes);
 1756                keeperSpell.setName(ConversionUtils.bytesToString(bytes).trim());
 1757                keeperSpell.setGuiIcon(readArtResource(file));
 1758                keeperSpell.setEditorIcon(readArtResource(file));
 1759                keeperSpell.setXc8(ConversionUtils.readInteger(file));
 1760                keeperSpell.setRechargeTime(ConversionUtils.readInteger(file) / ConversionUtils.FLOAT);
 1761                keeperSpell.setShotData1(ConversionUtils.readInteger(file));
 1762                keeperSpell.setShotData2(ConversionUtils.readInteger(file));
 1763                keeperSpell.setResearchTime(ConversionUtils.readUnsignedShort(file));
 1764                keeperSpell.setTargetRule(ConversionUtils.parseEnum((short) file.readUnsignedByte(), KeeperSpell.TargetRule.class));
 1765                keeperSpell.setOrderInEditor((short) file.readUnsignedByte());
 1766                keeperSpell.setFlags(ConversionUtils.parseFlagValue(ConversionUtils.readUnsignedInteger(file), KeeperSpell.KeeperSpellFlag.class));
 1767                keeperSpell.setXe0Unreferenced(ConversionUtils.readUnsignedShort(file));
 1768                keeperSpell.setManaDrain(ConversionUtils.readUnsignedShort(file));
      ...
```

## Mindustry:4fb0c246db0d:0 — ADD_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/4fb0c246db0d0a3d5b63c16ff5c0a374ad63fa57
- method: `TechTreeDialog.TechTreeDialog()` in `core/src/io/anuke/mindustry/ui/dialogs/TechTreeDialog.java`
- added statement (post-state): `Log.info("Missing items: ")`
- levels: None -> INFO

Pre-state:
```java
   29    public TechTreeDialog(){
   30            super("$techtree");
   31    
   32            layout = new TreeLayout();
   33            layout.gapBetweenLevels = 60f;
   34            layout.gapBetweenNodes = 40f;
   35            layout.layout(new TechTreeNode(TechTree.root, null));
   36            cont.add(new View()).grow();
   37    
   38            double total = Vars.content.recipes().count(r -> r.visibility == RecipeVisibility.all);
   39            if(total > nodes.size) Log.err("Recipe tree coverage: {0}%", (int)(nodes.size / total * 100));
   40    
   41            addCloseButton();
   42        }
```
Post-state:
```java
   32    public TechTreeDialog(){
   33            super("$techtree");
   34    
   35            TreeLayout layout = new TreeLayout();
   36            layout.gapBetweenLevels = 60f;
   37            layout.gapBetweenNodes = 40f;
   38            layout.layout(new TechTreeNode(TechTree.root, null));
   39            cont.add(new View()).grow();
   40    
   41            { //debug code
   42                ObjectSet<Recipe> used = new ObjectSet<>();
   43                for(TechTreeNode node : nodes){
   44                    if(node.node.block != null) used.add(Recipe.getByResult(node.node.block));
   45                }
   46                Array<Recipe> recipes = content.recipes().select(r -> r.visibility == RecipeVisibility.all && !used.contains(r));
   47                recipes.sort(Structs.comparing(r -> r.cost));
   48    
   49                if(recipes.size > 0){
   50                    Log.info("Recipe tree coverage: {0}%", (int)((float)nodes.size / content.recipes().select(r -> r.visibility == RecipeVisibility.all).size * 100));
   51 >>                 Log.info("Missing items: ");
   52                    recipes.forEach(r -> Log.info("    {0}", r));
   53                }
   54            }
   55    
   56            addCloseButton();
   57        }
```

## riiablo:30bd9408461d:2 — ADD_LOG

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/30bd9408461db376126b254bdaad6958d81ac2fc
- method: `BinkAudio.BinkAudio(BIK,ByteInput)` in `core/src/com/riiablo/video/BinkAudio.java`
- added statement (post-state): `log.trace("BANDS: {}", BANDS)`
- levels: None -> TRACE

Pre-state:
```java
   52    BinkAudio(BIK bik, ByteInput in) {
   53        this.bik = bik;
   54    
   55        log.trace("slicing {} bytes", SIZE);
   56        in = in.readSlice(SIZE);
   57    
   58        in.skipBytes(2); // unknown -- I've seen { 0x00, 0x1C }
   59    
   60        numChannels = in.readSafe16u();
   61        log.trace("numChannels: {}", numChannels);
   62        if (numChannels < 1 || numChannels > MAX_CHANNELS) {
   63          throw new InvalidFormat(in, "numChannels(" + numChannels + ") not in [" + 1 + ".." + MAX_CHANNELS + "]");
   64        }
   65    
   66        sampleRate = in.read16u();
   67        log.trace("sampleRate: {} Hz", sampleRate);
   68    
   69        flags = in.read16u();
   70        log.tracef("flags: 0x%04x (%s)", flags, getFlagsString());
   71    
   72        id = in.readSafe32u();
      ...
```
Post-state:
```java
      ...
   89        // if coded->id == RDFT then frameLen becomes 2f
   90    
   91        QUANTS = new float[96];
   92        for (int i = 0; i < 96; i++) {
   93          /* constant is result of 0.066399999/log10(M_E) */
   94          QUANTS[i] = (float) FastMath.exp(i * 0.15289164787221953823f) * root;
   95        }
   96        if (log.traceEnabled()) log.trace("QUANTS: {}", QUANTS);
   97    
   98        int numBands;
   99        for (numBands = 1; numBands < 25 && halfSampleRate > CRIT_FREQ[numBands - 1]; numBands++);
  100        this.numBands = numBands;
  101        log.trace("numBands: {}", numBands);
  102    
  103        BANDS = new int[numBands + 1];
  104        BANDS[0] = 2;
  105        for (int i = 1; i < numBands; i++) {
  106          BANDS[i] = (CRIT_FREQ[i - 1] * frameLen / halfSampleRate) & ~1;
  107        }
  108        BANDS[numBands] = frameLen;
  109 >>     if (log.traceEnabled()) log.trace("BANDS: {}", BANDS);
  110    
  111        first = true;
  112      }
```

## Mindustry:9dd6b9e74b73:4 — ADD_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/9dd6b9e74b734629d8f4535d2c6a3cd8096c9347
- method: `KryoServer.SocketServer.onClose(WebSocket,int,String,boolean)` in `kryonet/src/io/anuke/kryonet/KryoServer.java`
- added statement (post-state): `Log.info("&bLost web connection: {0}", k.id)`
- levels: None -> INFO

Pre-state:
```java
  398    @Override
  399            public void onClose(WebSocket conn, int code, String reason, boolean remote) {
  400                if (conn == null) return;
  401                KryoConnection k = getBySocket(conn);
  402                if(k == null) return;
  403                Disconnect disconnect = new Disconnect();
  404                disconnect.id = k.id;
  405                Net.handleServerReceived(k.id, disconnect);
  406            }
```
Post-state:
```java
  403    @Override
  404            public void onClose(WebSocket conn, int code, String reason, boolean remote) {
  405                if (conn == null) return;
  406    
  407                KryoConnection k = getBySocket(conn);
  408                if(k == null) return;
  409    
  410                Disconnect disconnect = new Disconnect();
  411                disconnect.id = k.id;
  412 >>             Log.info("&bLost web connection: {0}", k.id);
  413                Net.handleServerReceived(k.id, disconnect);
  414            }
```

## riiablo:a1e735031fdd:2 — ADD_LOG

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/a1e735031fdd2b886d66b39244c03204cb9ff743
- method: `LobbyScreen.show()` in `core/src/gdx/diablo/screen/LobbyScreen.java`
- added statement (post-state): `Gdx.app.log(TAG, "create-session " + error.toString())`
- levels: None -> INFO

Pre-state:
```java
   86    @Override
   87      public void show() {
   88        Diablo.assets.finishLoadingAsset(waitingroombkgdDescriptor);
   89        waitingroombkgd = Diablo.assets.get(waitingroombkgdDescriptor).getTexture();
   90    
   91        Diablo.assets.finishLoadingAsset(blankbckgDescriptor);
   92        blankbckg = Diablo.assets.get(blankbckgDescriptor).getTexture();
   93    
   94        Diablo.assets.finishLoadingAsset(creategamebckgDescriptor);
   95        creategamebckg = Diablo.assets.get(creategamebckgDescriptor).getTexture();
   96    
   97        Diablo.assets.finishLoadingAsset(joingamebckgDescriptor);
   98        joingamebckg = Diablo.assets.get(joingamebckgDescriptor).getTexture();
   99    
  100        stage.setDebugAll(true);
  101    
  102        ClickListener clickListener = new ClickListener() {
  103          @Override
  104          public void clicked(InputEvent event, float x, float y) {
  105            Actor actor = event.getListenerActor();
  106            if (actor == btnChannel) {
      ...
```
Post-state:
```java
      ...
  279                      desc     = tfDesc.getText();
  280                    }})
  281                    .build();
  282                Gdx.net.sendHttpRequest(request, new Net.HttpResponseListener() {
  283                  @Override
  284                  public void handleHttpResponse(Net.HttpResponse httpResponse) {
  285                    String response = httpResponse.getResultAsString();
  286                    try {
  287                      Session session = new Json().fromJson(Session.class, response);
  288                      Gdx.app.log(TAG, "create-session " + response);
  289    
  290                      Socket socket = null;
  291                      try {
  292                        socket = Gdx.net.newClientSocket(Net.Protocol.TCP, session.host, session.port, null);
  293                        Gdx.app.log(TAG, "create-session connect " + session.host + ":" + session.port + " " + socket.isConnected());
  294                      } finally {
  295                        if (socket != null) socket.dispose();
  296                      }
  297                    } catch (SerializationException e) {
  298                      SessionError error = new Json().fromJson(SessionError.class, response);
  299 >>                   Gdx.app.log(TAG, "create-session " + error.toString());
  300                    }
  301                  }
  302    
  303                  @Override
  304                  public void failed(Throwable t) {
  305                    Gdx.app.log(TAG, "create-session " + t.getMessage());
  306                  }
  307    
  308                  @Override
  309                  public void cancelled() {
  310                    Gdx.app.log(TAG, "create-session " + "cancelled");
  311                  }
  312                });
  313              }
  314            });
  315            tfGameName.addListener(new ChangeListener() {
  316              @Override
  317              public void changed(ChangeEvent event, Actor actor) {
  318                btnCreateGame.setDisabled(tfGameName.getText().isEmpty());
  319              }
      ...
```

## riiablo:bd9b30a33de5:2 — ADD_LOG

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/bd9b30a33de53214ae15e1fccabadb61cb88c9f3
- method: `MPQ.populateHashTable(ByteBuf)` in `core/src/com/riiablo/mpq_bytebuf/MPQ.java`
- added statement (post-state): `log.tracef(
            "decrypting hash table block %x+%x (%x)",
            hashTableOffset,
            hashTableBytes - remainingBytes,
            bufferBytes)`
- levels: None -> TRACE

Pre-state:
```java
  123    private void populateHashTable(final ByteBuf bb) {
  124        log.debugf("reading hash table...");
  125        log.trace("decrypting hash table...");
  126        bb.readerIndex(hashTableOffset);
  127        final ByteBuf hashTable = ALLOC.heapBuffer(hashTableSize * Entry.SIZE);
  128        try {
  129          bb.readBytes(hashTable);
  130          Decryptor.decrypt(Decryptor.HASH_TABLE_KEY, hashTable);
  131          int entries = 0;
  132          final Entry[] table = this.table;
  133          for (int i = 0, s = hashTableSize; i < s; i++) {
  134            final long key = hashTable.readLongLE();
  135            final int locale = hashTable.readUnsignedShortLE();
  136            final int platform = hashTable.readUnsignedShortLE();
  137            final long block = hashTable.readUnsignedIntLE();
  138            if (DEBUG_MODE) log.tracef("%08x %016x %04x %04x %08x", i, key, locale, platform, block);
  139    
  140            if (block >= archiveSize) {
  141              if (DEBUG_MODE && key != Entry.NULL_KEY) log.warnf(
  142                  "bad hash table entry %08x %016x %04x %04x %08x",
  143                  i, key, locale, platform, block);
      ...
```
Post-state:
```java
  145    private void populateHashTable(ByteBuf map) {
  146        log.debugf("reading hash table...");
  147    
  148        int i = 0;
  149        int files = 0;
  150        long encryption = ((long) Decryptor.SEED2 << Integer.SIZE) | (Decryptor.HASH_TABLE_KEY & 0xFFFFFFFFL);
  151        final Entry[] table = this.table;
  152    
  153        final ByteBuf buffer = obtainHeapBuffer(sectorSize);
  154        try {
  155          final int bufferSize = buffer.capacity();
  156          final int hashTableBytes = hashTableSize * Entry.SIZE;
  157          for (int remainingBytes = hashTableBytes; remainingBytes > 0; remainingBytes -= bufferSize) {
  158            final int bufferBytes = Math.min(remainingBytes, bufferSize);
  159            assert bufferBytes % Entry.SIZE == 0 : "bufferBytes(" + bufferBytes + ") does not evenly divide Entry.SIZE(" + Entry.SIZE + ")";
  160            int numEntries = bufferBytes / Entry.SIZE;
  161            assert map.readerIndex() == hashTableOffset + hashTableBytes - remainingBytes;
  162            map.readBytes(buffer.setIndex(0, 0), bufferBytes);
  163 >>         log.tracef(
  164                "decrypting hash table block %x+%x (%x)",
  165                hashTableOffset,
  166                hashTableBytes - remainingBytes,
  167                bufferBytes);
  168            final int encryptionKey = (int) (encryption & 0xFFFFFFFFL);
  169            final int encryptionSeed = (int) (encryption >>> Integer.SIZE);
  170            encryption = Decryptor.decrypt(encryptionKey, encryptionSeed, buffer);
  171            for (; --numEntries >= 0; i++) {
  172              final long key = buffer.readLongLE();
  173              final int locale = buffer.readUnsignedShortLE();
  174              final int platform = buffer.readUnsignedShortLE();
  175              final long block = buffer.readUnsignedIntLE();
  176              if (DEBUG_MODE) log.tracef("%04x %016x %04x %04x %08x", i, key, locale, platform, block);
  177    
  178              if (block >= archiveSize) {
  179                if (DEBUG_MODE && key != Entry.NULL_KEY) log.warnf(
  180                    "bad hash table entry %08x %016x %04x %04x %08x",
  181                    i, key, locale, platform, block);
  182                table[i] = block == Entry.BLOCK_UNUSED ? Entry.UNUSED : Entry.DELETED;
  183              } else {
      ...
```

## riiablo:52a5508167fa:1 — ADD_LOG

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/52a5508167fa7bb1a592cd642a3e62de86b27b61
- method: `ItemWriter.writeItem(Item,ByteOutput)` in `core/src/com/riiablo/item/ItemWriter.java`
- added statement (post-state): `log.debug("size: {} (0x{}) (+{} .. +{})",
          itemSize,
          Integer.toHexString(itemSize),
          Integer.toHexString(startOffset),
          Integer.toHexString(endOffset))`
- levels: None -> DEBUG

Pre-state:
```java
   20    public ByteOutput writeItem(Item item, ByteOutput out) {
   21        writeSingleItem(item, out);
   22        if (item.socketsFilled > 0) log.trace("Writing {} sockets...", item.socketsFilled);
   23        for (int i = 0; i < item.socketsFilled; i++) {
   24          try {
   25            Log.put("socket", i);
   26            Item socket = item.sockets.get(i);
   27            writeSingleItem(socket, out);
   28          } finally {
   29            Log.remove("socket");
   30          }
   31        }
   32        return out;
   33      }
```
Post-state:
```java
   21    public ByteOutput writeItem(Item item, ByteOutput out) {
   22        final int startOffset = out.bytesWritten();
   23        writeSingleItem(item, out);
   24        if (item.socketsFilled > 0) log.trace("Writing {} sockets...", item.socketsFilled);
   25        for (int i = 0; i < item.socketsFilled; i++) {
   26          try {
   27            Log.put("socket", i);
   28            Item socket = item.sockets.get(i);
   29            writeSingleItem(socket, out);
   30          } finally {
   31            Log.remove("socket");
   32          }
   33        }
   34        if (log.isDebugEnabled()) {
   35          final int endOffset = out.bytesWritten();
   36          final int itemSize = endOffset - startOffset;
   37 >>       log.debug("size: {} (0x{}) (+{} .. +{})",
   38              itemSize,
   39              Integer.toHexString(itemSize),
   40              Integer.toHexString(startOffset),
   41              Integer.toHexString(endOffset));
   42          if (log.isTraceEnabled()) {
   43            Log.tracef(log, "bytes: %n%s", ByteBufUtil.prettyHexDump(out.buffer()));
   44          } else {
   45            log.debug("bytes: {}", ByteBufUtil.hexDump(out.buffer()));
   46          }
   47        }
   48        return out;
   49      }
```

## Mindustry:7429d029f3b6:0 — ADD_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/7429d029f3b65ba2972a2f2744a1a3b3ddeaa1ec
- method: `NetServer.NetServer()` in `core/src/io/anuke/mindustry/core/NetServer.java`
- added statement (post-state): `Log.err("ACCESS DENIED: Player {0} / {1} attempted to perform admin action without proper security access.",
                        player.name, Net.getConnection(player.clientid).address)`
- levels: None -> ERROR

Pre-state:
```java
   53    public NetServer(){
   54    
   55            Events.on(GameOverEvent.class, () -> weapons.clear());
   56    
   57            Net.handleServer(Connect.class, (id, connect) -> {
   58                if(admins.isBanned(connect.addressTCP)){
   59                    Net.kickConnection(id, KickReason.banned);
   60                }
   61            });
   62    
   63            Net.handleServer(ConnectPacket.class, (id, packet) -> {
   64                if(Net.getConnection(id) == null ||
   65                        admins.isBanned(Net.getConnection(id).address)) return;
   66    
   67                admins.setKnownName(Net.getConnection(id).address, packet.name);
   68    
   69                if(packet.version != Version.build && Version.build != -1){
   70                    if(packet.version == -1){
   71                        admins.banPlayer(Net.getConnection(id).address);
   72                        Net.kickConnection(id, KickReason.banned);
   73                    }else {
      ...
```
Post-state:
```java
      ...
  228                int id = packet.id;
  229                int dest = cid;
  230                EntityGroup group = Entities.getGroup(packet.group);
  231                if(group.getByID(id) != null){
  232                    EntitySpawnPacket p = new EntitySpawnPacket();
  233                    p.entity = (SyncEntity)group.getByID(id);
  234                    p.group = group;
  235                    Net.sendTo(dest, p, SendMode.tcp);
  236                }
  237            });
  238    
  239            Net.handleServer(PlayerDeathPacket.class, (id, packet) -> {
  240                packet.id = connections.get(id).id;
  241                Net.sendExcept(id, packet, SendMode.tcp);
  242            });
  243    
  244            Net.handleServer(AdministerRequestPacket.class, (id, packet) -> {
  245                Player player = connections.get(id);
  246    
  247                if(!player.isAdmin){
  248 >>                 Log.err("ACCESS DENIED: Player {0} / {1} attempted to perform admin action without proper security access.",
  249                            player.name, Net.getConnection(player.clientid).address);
  250                    return;
  251                }
  252    
  253                Player other = playerGroup.getByID(packet.id);
  254    
  255                if(other == null){
  256                    Log.err("{0} attempted to perform admin action on nonexistant player.", player.name);
  257                    return;
  258                }
  259    
  260                if(packet.action == AdminAction.ban){
  261                    admins.banPlayer(Net.getConnection(other.clientid).address);
  262                    Net.kickConnection(other.clientid, KickReason.banned);
  263                    Log.info("&lc{0} has banned {1}.", player.name, other.name);
  264                }else if(packet.action == AdminAction.kick){
  265                    Net.kickConnection(other.clientid, KickReason.kick);
  266                    Log.info("&lc{0} has kicked {1}.", player.name, other.name);
  267                }
  268            });
      ...
```

## Mindustry:9dd6b9e74b73:0 — ADD_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/9dd6b9e74b734629d8f4535d2c6a3cd8096c9347
- method: `NetServer.NetServer()` in `core/src/io/anuke/mindustry/core/NetServer.java`
- added statement (post-state): `Log.info("&y{0} has connected.", player.name)`
- levels: None -> INFO

Pre-state:
```java
   39    public NetServer(){
   40    
   41            Net.handleServer(Connect.class, (id, connect) -> {});
   42    
   43            Net.handleServer(ConnectPacket.class, (id, packet) -> {
   44    
   45                if(packet.version != Net.version){
   46                    Net.kickConnection(id, packet.version > Net.version ? KickReason.serverOutdated : KickReason.clientOutdated);
   47                    return;
   48                }
   49    
   50                Log.info("Sending world data to client (ID = {0})", id);
   51    
   52                Player player = new Player();
   53                player.clientid = id;
   54                player.name = packet.name;
   55                player.isAndroid = packet.android;
   56                player.set(world.getSpawnX(), world.getSpawnY());
   57                player.interpolator.last.set(player.x, player.y);
   58                player.interpolator.target.set(player.x, player.y);
   59                player.color.set(packet.color);
      ...
```
Post-state:
```java
      ...
   76            });
   77    
   78            Net.handleServer(MapAckPacket.class, (id, packet) -> {
   79                Player player = connections.get(id);
   80    
   81                ByteArrayOutputStream stream = new ByteArrayOutputStream();
   82                NetworkIO.writeWorld(player.id, weapons.get(player.name, new ByteArray()), stream);
   83                WorldData data = new WorldData();
   84                data.stream = new ByteArrayInputStream(stream.toByteArray());
   85                Net.sendStream(id, data);
   86    
   87                Log.info("Packed {0} uncompressed bytes of WORLD data.", stream.size());
   88            });
   89    
   90            Net.handleServer(ConnectConfirmPacket.class, (id, packet) -> {
   91                Player player = connections.get(id);
   92    
   93                if (player == null) return;
   94    
   95                player.add();
   96 >>             Log.info("&y{0} has connected.", player.name);
   97                netCommon.sendMessage("[accent]" + player.name + " has connected.");
   98            });
   99    
  100            Net.handleServer(Disconnect.class, (id, packet) -> {
  101                Player player = connections.get(packet.id);
  102    
  103                if (player == null) {
  104                    Log.err("Unknown client has disconnected (ID={0})", id);
  105                    return;
  106                }
  107    
  108                Log.info("&y{0} has disconnected.", player.name);
  109                netCommon.sendMessage("[accent]" + player.name + " has disconnected.");
  110                player.remove();
  111    
  112                DisconnectPacket dc = new DisconnectPacket();
  113                dc.playerid = player.id;
  114    
  115                Net.send(dc, SendMode.tcp);
  116    
      ...
```

## Mindustry:fabc02f6ef3a:0 — ADD_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/fabc02f6ef3ac4ba221d817b439d1fa1170d70cc
- method: `ServerControl.ServerControl()` in `core/src/io/anuke/mindustry/core/ServerControl.java`
- added statement (post-state): `info("Game over!")`
- levels: None -> INFO

Pre-state:
```java
   35    public ServerControl(){
   36            Effects.setScreenShakeProvider((a, b) -> {});
   37            Effects.setEffectProvider((a, b, c, d, e) -> {});
   38            Sounds.setHeadless(true);
   39    
   40            //override default handling of chat packets
   41            Net.handle(ChatPacket.class, (packet) -> {
   42                info("&y" + (packet.name == null ? "" : packet.name) +  ": &lb{0}", packet.text);
   43            });
   44    
   45            //don't do anything at all for GDX logging
   46            Gdx.app.setApplicationLogger(new ApplicationLogger() {
   47                @Override public void log(String tag, String message) { }
   48                @Override public void log(String tag, String message, Throwable exception) { }
   49                @Override public void error(String tag, String message) { }
   50                @Override public void error(String tag, String message, Throwable exception) { }
   51                @Override public void debug(String tag, String message) { }
   52                @Override public void debug(String tag, String message, Throwable exception) { }
   53            });
   54    
   55            registerCommands();
      ...
```
Post-state:
```java
      ...
   47            Net.handle(ChatPacket.class, (packet) -> {
   48                info("&y" + (packet.name == null ? "" : packet.name) +  ": &lb{0}", packet.text);
   49            });
   50    
   51            //don't do anything at all for GDX logging
   52            Gdx.app.setApplicationLogger(new ApplicationLogger() {
   53                @Override public void log(String tag, String message) { }
   54                @Override public void log(String tag, String message, Throwable exception) { }
   55                @Override public void error(String tag, String message) { }
   56                @Override public void error(String tag, String message, Throwable exception) { }
   57                @Override public void debug(String tag, String message) { }
   58                @Override public void debug(String tag, String message, Throwable exception) { }
   59            });
   60    
   61            registerCommands();
   62            Thread thread = new Thread(this::readCommands, "Server Controls");
   63            thread.setDaemon(true);
   64            thread.start();
   65    
   66            Events.on(GameOverEvent.class, () -> {
   67 >>             info("Game over!");
   68    
   69                Timers.runTask(10f, () -> {
   70                    Net.closeServer();
   71    
   72                    if(shuffle) {
   73                        Map previous = world.getMap();
   74                        Map map = previous;
   75                        while(map == previous) map = world.maps().getDefaultMaps().random();
   76    
   77                        info("Selected next map to be {0}.", map.name);
   78                        state.set(State.playing);
   79                        logic.reset();
   80                        world.loadMap(map);
   81                        host();
   82                    }else{
   83                        state.set(State.menu);
   84                    }
   85                });
   86            });
   87    
      ...
```

## Mindustry:a9f11256cdb6:0 — ADD_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/a9f11256cdb67756fe176607f0e783032410498b
- method: `Block.init()` in `core/src/io/anuke/mindustry/world/Block.java`
- added statement (post-state): `Log.warn("No name for block '{0}' found. Add the following to bundle.properties:\nblock.{0}.name = {1}", name, Strings.capitalize(name))`
- levels: None -> WARN

Pre-state:
```java
  268    @Override
  269        public void init(){
  270            //initialize default health based on size
  271            if(health == -1){
  272                health = size * size * 40;
  273            }
  274    
  275            buildCost = 0f;
  276            for(ItemStack stack : buildRequirements){
  277                buildCost += stack.amount * stack.item.cost;
  278            }
  279    
  280            setStats();
  281    
  282            consumes.checkRequired(this);
  283        }
```
Post-state:
```java
  270    @Override
  271        public void init(){
  272            //initialize default health based on size
  273            if(health == -1){
  274                health = size * size * 40;
  275            }
  276    
  277            buildCost = 0f;
  278            for(ItemStack stack : buildRequirements){
  279                buildCost += stack.amount * stack.item.cost;
  280            }
  281    
  282            setStats();
  283    
  284            consumes.checkRequired(this);
  285    
  286            if(buildRequirements.length > 0 && !Core.bundle.has("block." + name + ".name")){
  287 >>             Log.warn("No name for block '{0}' found. Add the following to bundle.properties:\nblock.{0}.name = {1}", name, Strings.capitalize(name));
  288            }
  289        }
```

## Mindustry:8704e14fd703:0 — ADD_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/8704e14fd7039e1ab218f740b1a7ecb7cf5dbb98
- method: `NetClient.blockSnapshot(short,short,byte[])` in `core/src/mindustry/core/NetClient.java`
- added statement (post-state): `Log.warn("Block ID mismatch at @: @ != @. Skipping block snapshot.", tile, tile.build.block.id, block)`
- levels: None -> WARN

Pre-state:
```java
  440    @Remote(variants = Variant.both, priority = PacketPriority.low, unreliable = true)
  441        public static void blockSnapshot(short amount, short dataLen, byte[] data){
  442            try{
  443                netClient.byteStream.setBytes(net.decompressSnapshot(data, dataLen));
  444                DataInputStream input = netClient.dataStream;
  445    
  446                for(int i = 0; i < amount; i++){
  447                    int pos = input.readInt();
  448                    Tile tile = world.tile(pos);
  449                    if(tile == null || tile.build == null){
  450                        Log.warn("Missing entity at @. Skipping block snapshot.", tile);
  451                        break;
  452                    }
  453                    tile.build.readAll(Reads.get(input), tile.build.version());
  454                }
  455            }catch(Exception e){
  456                Log.err(e);
  457            }
  458        }
```
Post-state:
```java
  440    @Remote(variants = Variant.both, priority = PacketPriority.low, unreliable = true)
  441        public static void blockSnapshot(short amount, short dataLen, byte[] data){
  442            try{
  443                netClient.byteStream.setBytes(net.decompressSnapshot(data, dataLen));
  444                DataInputStream input = netClient.dataStream;
  445    
  446                for(int i = 0; i < amount; i++){
  447                    int pos = input.readInt();
  448                    short block = input.readShort();
  449                    Tile tile = world.tile(pos);
  450                    if(tile == null || tile.build == null){
  451                        Log.warn("Missing entity at @. Skipping block snapshot.", tile);
  452                        break;
  453                    }
  454                    if(tile.build.block.id != block){
  455 >>                     Log.warn("Block ID mismatch at @: @ != @. Skipping block snapshot.", tile, tile.build.block.id, block);
  456                        break;
  457                    }
  458                    tile.build.readAll(Reads.get(input), tile.build.version());
  459                }
  460            }catch(Exception e){
  461                Log.err(e);
  462            }
  463        }
```

## subspace-infinity:14e400d01509:7 — ADD_LOG

- repo: subspace-infinity  commit: https://github.com/assofohdz/subspace-infinity/commit/14e400d015090529e1a9060d2c7fd3ce827e5897
- method: `SimplePhysics.removeBody(EntityId)` in `subspace-infinity/src/main/java/infinity/sim/SimplePhysics.java`
- added statement (post-state): `log.info("Number of statics in play: " + indexStatic.size())`
- levels: None -> INFO

Pre-state:
```java
  222    protected boolean removeBody(EntityId entityId) {
  223            SimpleBody result = index.remove(entityId);
  224            if (result != null) {
  225                toRemove.add(result);
  226                return true;
  227            }
  228            return false;
  229        }
```
Post-state:
```java
  229    protected boolean removeBody(EntityId entityId) {
  230            SimpleBody result = index.remove(entityId);
  231            if (result != null) {
  232                log.info("Number of dynamics in play: " + index.size());
  233                toRemove.add(result);
  234                return true;
  235            }
  236            result = indexStatic.remove(entityId);
  237            if (result != null) {
  238 >>             log.info("Number of statics in play: " + indexStatic.size());
  239                toRemove.add(result);
  240                return true;
  241            }
  242            return false;
  243        }
```

## riiablo:49f105856642:1 — ADD_LOG

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/49f10585664276092435bd4f1987644f47f87599
- method: `GameScreen.show()` in `core/src/gdx/diablo/screen/GameScreen.java`
- added statement (post-state): `Gdx.app.log(TAG, "connecting to " + socket.getRemoteAddress() + "...")`
- levels: None -> INFO

Pre-state:
```java
  297    @Override
  298      public void show() {
  299        Diablo.music.stop();
  300        Diablo.assets.get(windowopenDescriptor).play();
  301    
  302        map = Diablo.assets.get(mapDescriptor);
  303        camera = new OrthographicCamera(Diablo.VIRTUAL_WIDTH, Diablo.VIRTUAL_HEIGHT);
  304        mapRenderer = new MapRenderer(Diablo.batch, camera);
  305        mapRenderer.setMap(map);
  306        mapRenderer.resize();
  307    
  308        GridPoint2 origin = map.find(Map.ID.TOWN_ENTRY_1);
  309        mapRenderer.setPosition(origin);
  310        if (Gdx.app.getType() == Application.ApplicationType.Android) {
  311          camera.zoom = 0.80f;
  312          camera.update();
  313        }
  314    
  315        //character.x = origin.x;
  316        //character.y = origin.y;
  317        player.origin().set(origin);
      ...
```
Post-state:
```java
      ...
  364    
  365        Keys.Esc.addStateListener(mappedKeyStateListener);
  366        Keys.Inventory.addStateListener(mappedKeyStateListener);
  367        Keys.Character.addStateListener(mappedKeyStateListener);
  368        Keys.Stash.addStateListener(mappedKeyStateListener);
  369        Keys.SwapWeapons.addStateListener(mappedKeyStateListener);
  370        Keys.Enter.addStateListener(mappedKeyStateListener);
  371        Diablo.input.addProcessor(stage);
  372        Diablo.input.addProcessor(inputProcessorTest);
  373    
  374        updateTask = Timer.schedule(new Timer.Task() {
  375          @Override
  376          public void run() {
  377            if (UIUtils.shift()) return;
  378            player.move();
  379            mapRenderer.setPosition(player.origin());
  380          }
  381        }, 0, 1 / 25f);
  382    
  383        if (socket != null && socket.isConnected()) {
  384 >>       Gdx.app.log(TAG, "connecting to " + socket.getRemoteAddress() + "...");
  385          in = IOUtils.buffer(new InputStreamReader(socket.getInputStream()));
  386          out = new PrintWriter(socket.getOutputStream(), true);
  387        }
  388      }
```

## OpenRTS:40e03e6dc990:13 — ADD_LOG

- repo: OpenRTS  commit: https://github.com/methusalah/OpenRTS/commit/40e03e6dc9902e3b5ab7b0ed3ac5088514bbcb78
- method: `MapFactory.load()` in `RTSForGit/src/model/map/MapFactory.java`
- added statement (post-state): `LogUtil.logger.info("   builders")`
- levels: None -> INFO

Pre-state:
```java
   46    public Map load(){
   47            Map res = null;
   48            final JFileChooser fc = new JFileChooser("assets/maps");
   49            int returnVal = fc.showOpenDialog(null);
   50            if (returnVal==JFileChooser.APPROVE_OPTION) {
   51                    File f = fc.getSelectedFile();
   52                    try {
   53                        res = load(f);
   54                    } catch (Exception e1) {
   55                            e1.printStackTrace();
   56                    }
   57            }
   58            if(res == null){
   59                LogUtil.logger.info("Load failed");
   60                return null;
   61            }
   62            
   63            lib.getMapStyleBuilder(res.mapStyleID).build(res);
   64            linkTiles(res);
   65            
   66            for(Tile t : res.tiles)
      ...
```
Post-state:
```java
   53    public Map load(){
   54            Map res = null;
   55            final JFileChooser fc = new JFileChooser(Model.DEFAULT_MAP_PATH);
   56            int returnVal = fc.showOpenDialog(null);
   57            if (returnVal == JFileChooser.APPROVE_OPTION) {
   58                    File f = fc.getSelectedFile();
   59                    try {
   60                        LogUtil.logger.info("Loading map "+f.getCanonicalPath()+"...");
   61                        res = load(f);
   62                    } catch (Exception e1) {
   63                            e1.printStackTrace();
   64                    }
   65            }
   66            if(res == null){
   67                LogUtil.logger.info("Load failed");
   68                return null;
   69            }
   70            
   71 >>         LogUtil.logger.info("   builders");
   72            lib.getMapStyleBuilder(res.mapStyleID).build(res);
   73    
   74            LogUtil.logger.info("   tiles' links");
   75            linkTiles(res);
   76            
   77            for(Tile t : res.tiles)
   78                if(t.isCliff)
   79                    t.setCliff();
   80            
   81            LogUtil.logger.info("   cliffs' connexions");
   82            for(Tile t : res.tiles){
   83                t.correctElevation();
   84                if(t.isCliff)
   85                    t.cliff.connect();
   86            }
   87    
   88            LogUtil.logger.info("   cliffs' shapes");
   89            for(Tile t : res.tiles){
   90                if(t.isCliff)
   91                    lib.getCliffShapeBuilder(t.cliffShapeID).build(t.cliff);
      ...
```

## riiablo:a8e2402a19ea:7 — ADD_LOG

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/a8e2402a19ea3c388fb3b83c3e256ed9bbf2c32b
- method: `ItemSerializer.readQualityData(BitStream,Item)` in `core/src/com/riiablo/item/ItemSerializer.java`
- added statement (post-state): `log.trace("qualityId: {}", item.qualityId)`
- levels: None -> TRACE

Pre-state:
```java
   88    private static boolean readQualityData(BitStream bitStream, Item item) {
   89        switch (item.quality) {
   90          case LOW:
   91          case HIGH:
   92            item.qualityId = bitStream.readUnsigned31OrLess(3);
   93            return true;
   94    
   95          case NORMAL:
   96            item.qualityId = 0;
   97            return true;
   98    
   99          case SET:
  100            item.qualityId = bitStream.readUnsigned31OrLess(Item.SET_ID_SIZE);
  101            item.qualityData = Riiablo.files.SetItems.get(item.qualityId);
  102            if (item.qualityId == (1 << Item.SET_ID_SIZE) - 1) {
  103              Gdx.app.error(TAG, String.format("Unknown set id: 0x%03x", item.qualityId));
  104            }
  105            return true;
  106    
  107          case UNIQUE:
  108            item.qualityId = bitStream.readUnsigned31OrLess(Item.UNIQUE_ID_SIZE);
      ...
```
Post-state:
```java
      ...
  153          case UNIQUE:
  154            item.qualityId = bitStream.readUnsigned31OrLess(Item.UNIQUE_ID_SIZE);
  155            log.trace("qualityId: {}", item.qualityId);
  156            item.qualityData = Riiablo.files.UniqueItems.get(item.qualityId);
  157            log.trace("qualityData: {}", item.qualityData);
  158            if (item.qualityId == (1 << Item.UNIQUE_ID_SIZE) - 1) {
  159              log.warn("Unknown unique item id: {}", item.qualityId);
  160              // This is expected for hdm and possibly others
  161              // TODO: ensure item can be gracefully handled, else throw item format exception
  162            }
  163            return true;
  164    
  165          case MAGIC:
  166            item.qualityId = bitStream.readUnsigned31OrLess(2 * Item.MAGIC_AFFIX_SIZE); // 11 for prefix, 11 for suffix
  167            log.trace("qualityId: {}", item.qualityId);
  168            return true;
  169    
  170          case RARE:
  171          case CRAFTED:
  172            item.qualityId = bitStream.readUnsigned31OrLess(2 * Item.RARE_AFFIX_SIZE); // 8 for prefix, 8 for suffix
  173 >>         log.trace("qualityId: {}", item.qualityId);
  174            item.qualityData = new RareQualityData(bitStream);
  175            log.trace("qualityData: {}", item.qualityData);
  176            return true;
  177    
  178          default:
  179            item.qualityId = 0;
  180            return false;
  181        }
  182      }
```

## riiablo:bebcf9068384:0 — ADD_LOG

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/bebcf906838410cd9b9eb6d14632abd525180bc7
- method: `DecodingService.DecodingService(int)` in `core/src/main/java/com/riiablo/mpq_bytebuf/DecodingService.java`
- added statement (post-state): `log.warn("Problem occurred while trying to add runtime shutdown hook.", t)`
- levels: None -> WARN

Pre-state:
```java
   47    DecodingService(int nThreads) {
   48        super(nThreads);
   49      }
```
Post-state:
```java
   54    DecodingService(int nThreads) {
   55        super(nThreads);
   56        try {
   57          Runtime.getRuntime().addShutdownHook(shutdownHook);
   58        } catch (Throwable t) {
   59 >>       log.warn("Problem occurred while trying to add runtime shutdown hook.", t);
   60        }
   61      }
```

## OpenKeeper:3684145f5538:7 — ADD_LOG

- repo: OpenKeeper  commit: https://github.com/tonihele/OpenKeeper/commit/3684145f553823ffd9791b11d6e4ffd7d8490c3a
- method: `KwdFile.readEffectElements(KwdHeader,RandomAccessFile)` in `src/toniarts/opendungeonkeeper/tools/convert/map/KwdFile.java`
- added statement (post-state): `logger.info("Reading effect elements!")`
- levels: None -> INFO

Pre-state:
```java
 1365    private void readEffectElements(String dkIIPath) throws RuntimeException {
 1366    
 1367            // Read the effect elements catalog
 1368            File effectElementsFile = new File(dkIIPath.concat("Data").concat(File.separator).concat("editor").concat(File.separator).concat("EffectElements.kwd"));
 1369            try (RandomAccessFile raweffectElements = new RandomAccessFile(effectElementsFile, "r")) {
 1370    
 1371                // Effect elements file has a 36 header
 1372                raweffectElements.seek(20);
 1373                int effectElementsCount = Utils.readUnsignedInteger(raweffectElements);
 1374    
 1375                // The effect elements file is just simple blocks until EOF
 1376                raweffectElements.seek(36); // End of header
 1377                raweffectElements.skipBytes(20); // I don't know what is in here
 1378    
 1379                effectElements = new HashMap<>(effectElementsCount);
 1380                for (int i = 0; i < effectElementsCount; i++) {
 1381                    EffectElement effectElement = new EffectElement();
 1382                    byte[] bytes = new byte[32];
 1383                    raweffectElements.read(bytes);
 1384                    effectElement.setName(Utils.bytesToString(bytes).trim());
 1385                    effectElement.setArtResource(readArtResource(raweffectElements));
      ...
```
Post-state:
```java
 1465    private void readEffectElements(KwdHeader header, RandomAccessFile file) throws IOException {
 1466    
 1467            // Read the effect elements catalog
 1468 >>         logger.info("Reading effect elements!");
 1469            effectElements = new HashMap<>(header.getItemCount());
 1470            for (int i = 0; i < header.getItemCount(); i++) {
 1471                long offset = file.getFilePointer();
 1472                EffectElement effectElement = new EffectElement();
 1473                byte[] bytes = new byte[32];
 1474                file.read(bytes);
 1475                effectElement.setName(Utils.bytesToString(bytes).trim());
 1476                effectElement.setArtResource(readArtResource(file));
 1477                effectElement.setMass(Utils.readInteger(file) / FIXED_POINT_DIVISION);
 1478                effectElement.setAirFriction(Utils.readUnsignedInteger(file) / FIXED_POINT5_DIVISION);
 1479                effectElement.setElasticity(Utils.readUnsignedInteger(file) / FIXED_POINT5_DIVISION);
 1480                effectElement.setMinSpeedXy(Utils.readInteger(file) / FIXED_POINT_DIVISION);
 1481                effectElement.setMaxSpeedXy(Utils.readInteger(file) / FIXED_POINT_DIVISION);
 1482                effectElement.setMinSpeedYz(Utils.readInteger(file) / FIXED_POINT_DIVISION);
 1483                effectElement.setMaxSpeedYz(Utils.readInteger(file) / FIXED_POINT_DIVISION);
 1484                effectElement.setMinScale(Utils.readUnsignedInteger(file) / FIXED_POINT_DIVISION);
 1485                effectElement.setMaxScale(Utils.readUnsignedInteger(file) / FIXED_POINT_DIVISION);
 1486                effectElement.setScaleRatio(Utils.readUnsignedInteger(file) / FIXED_POINT_DIVISION);
 1487                effectElement.setFlags(Utils.readUnsignedInteger(file));
 1488                effectElement.setEffectElementId(Utils.readUnsignedShort(file));
      ...
```

## riiablo:7a2dfeb18ace:9 — ADD_LOG

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/7a2dfeb18ace64f5f41ddded32e889c84a8d0c3e
- method: `MapViewer.create()` in `tools/map-viewer/src/main/java/com/riiablo/map/MapViewer.java`
- added statement (post-state): `log.infof("seed: %08x", seed)`
- levels: None -> INFO

Pre-state:
```java
  158    @Override
  159      public void create() {
  160        Gdx.app.setLogLevel(Application.LOG_DEBUG);
  161    
  162        Riiablo.home = home = Gdx.files.absolute(home.path());
  163        MPQFileHandleResolver resolver = Riiablo.mpqs = new MPQFileHandleResolver();
  164    
  165        AssetManager assets = Riiablo.assets = new AssetManager();
  166        assets.setLoader(DS1.class, new DS1Loader(resolver));
  167        assets.setLoader(DT1.class, new DT1Loader(resolver));
  168        assets.setLoader(COF.class, new COFLoader(resolver));
  169        assets.setLoader(DCC.class, new DCCLoader(resolver));
  170        assets.setLoader(DC6.class, new DC6Loader(resolver));
  171        assets.setLoader(Palette.class, new PaletteLoader(resolver));
  172        assets.setLoader(FontTBL.BitmapFont.class, new BitmapFontLoader(resolver));
  173    
  174        font = new BitmapFont();
  175    
  176        Riiablo.files = new Files(assets);
  177        Riiablo.fonts = new Fonts(assets);
  178        Riiablo.palettes = new Palettes(assets);
      ...
```
Post-state:
```java
  251    @Override
  252      public void create() {
  253        Gdx.app.setLogLevel(Application.LOG_DEBUG);
  254        LogManager.setLevel(MapViewer.class.getName(), Level.DEBUG);
  255    
  256        Riiablo.home = home = Gdx.files.absolute(home.path());
  257        MPQFileHandleResolver resolver = Riiablo.mpqs = new MPQFileHandleResolver();
  258    
  259        if (seed == -1) seed = MathUtils.random.nextInt();
  260 >>     log.infof("seed: %08x", seed);
  261    
  262        AssetManager assets = Riiablo.assets = new AssetManager();
  263        assets.setLoader(DS1.class, new DS1Loader(resolver));
  264        assets.setLoader(DT1.class, new DT1Loader(resolver));
  265        assets.setLoader(COF.class, new COFLoader(resolver));
  266        assets.setLoader(DCC.class, new DCCLoader(resolver));
  267        assets.setLoader(DC6.class, new DC6Loader(resolver));
  268        assets.setLoader(Palette.class, new PaletteLoader(resolver));
  269        assets.setLoader(FontTBL.BitmapFont.class, new BitmapFontLoader(resolver));
  270    
  271        font = new BitmapFont();
  272    
  273        Riiablo.files = new Files(assets);
  274        Riiablo.fonts = new Fonts(assets);
  275        Riiablo.palettes = new Palettes(assets);
  276        Riiablo.colors = new Colors();
  277        Riiablo.textures = new Textures();
  278        Riiablo.string = new StringTBLs(resolver);
  279        Riiablo.cofs = new COFs(assets);//COFD2.loadFromFile(resolver.resolve("data\\global\\cmncof_a1.d2"));
  280        Riiablo.anim = D2.loadFromFile(resolver.resolve("data\\global\\eanimdata.d2"));
      ...
```

## Mindustry:ddac5cbfbcb9:0 — ADD_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/ddac5cbfbcb93392b0ec0fa01d7c794852021bad
- method: `UnitType.UnitType()` in `core/src/io/anuke/mindustry/entities/units/UnitType.java`
- added statement (post-state): `Log.err("Warning: unit '" + name + "' is missing a localized name. Add the follow to bundle.properties:")`
- levels: None -> ERROR

Pre-state:
```java
   50    public <T extends BaseUnit> UnitType(String name, Class<T> type, Supplier<T> mainConstructor){
   51            this.id = lastid++;
   52            this.name = name;
   53            this.constructor = mainConstructor;
   54    
   55            types.add(this);
   56    
   57            TypeTrait.registerType(type, mainConstructor);
   58        }
```
Post-state:
```java
   55    public <T extends BaseUnit> UnitType(String name, Class<T> type, Supplier<T> mainConstructor){
   56            this.id = lastid++;
   57            this.name = name;
   58            this.constructor = mainConstructor;
   59            this.description = Bundles.getOrNull("unit." + name + ".description");
   60    
   61            types.add(this);
   62    
   63            TypeTrait.registerType(type, mainConstructor);
   64    
   65            if(!Bundles.has("unit." + this.name + ".name")){
   66 >>             Log.err("Warning: unit '" + name + "' is missing a localized name. Add the follow to bundle.properties:");
   67                Log.err("unit." + this.name + ".name=" + Strings.capitalize(name.replace('-', '_')));
   68            }
   69        }
```

## Mindustry:1dedefd56c29:0 — ADD_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/1dedefd56c29769ee468df73079b7d4d637d1416
- method: `Schematics.load()` in `core/src/mindustry/game/Schematics.java`
- added statement (post-state): `Log.err(Strings.format("Failed to create shadow buffer (@x@): @. This is likely because a mod is setting maxSchematicSize too high. Don't do that.",
                    maxSchematicSize + padding + 8,`
- levels: None -> ERROR

Pre-state:
```java
   78    public void load(){
   79            all.clear();
   80    
   81            loadLoadouts();
   82    
   83            schematicDirectory.walk(file -> {
   84                if(file.extEquals(schematicExtension)){
   85                    loadFile(file);
   86                }
   87            });
   88    
   89            platform.getWorkshopContent(Schematic.class).each(this::loadFile);
   90    
   91            //mod-specific schematics, cannot be removed
   92            mods.listFiles("schematics", (mod, file) -> {
   93                Schematic s = loadFile(file);
   94                if(s != null){
   95                    s.mod = mod;
   96                }
   97            });
   98    
      ...
```
Post-state:
```java
      ...
   86                }
   87            });
   88    
   89            platform.getWorkshopContent(Schematic.class).each(this::loadFile);
   90    
   91            //mod-specific schematics, cannot be removed
   92            mods.listFiles("schematics", (mod, file) -> {
   93                Schematic s = loadFile(file);
   94                if(s != null){
   95                    s.mod = mod;
   96                }
   97            });
   98    
   99            all.sort();
  100    
  101            if(shadowBuffer == null && !headless){
  102                Core.app.post(() -> {
  103                    try{
  104                        shadowBuffer = new FrameBuffer(maxSchematicSize + padding + 8, maxSchematicSize + padding + 8);
  105                    }catch(Exception e){
  106 >>                     Log.err(Strings.format("Failed to create shadow buffer (@x@): @. This is likely because a mod is setting maxSchematicSize too high. Don't do that.",
  107                        maxSchematicSize + padding + 8, maxSchematicSize + padding + 8, Strings.getSimpleMessage(e)));
  108                    }
  109                });
  110            }
  111        }
```

## riiablo:31960a83a133:12 — ADD_LOG

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/31960a83a133831a01eec57caa2746cb09eacc53
- method: `DccLoader.loadAsync(AssetManager,AssetDesc<Dcc>,F,Object)` in `core/src/main/java/com/riiablo/asset/loader/DccLoader.java`
- added statement (post-state): `log.trace("decoding {}", asset)`
- levels: None -> TRACE

Pre-state:
```java
   71    @Override
   72      protected <F extends FileHandle> Dcc loadAsync(
   73          AssetManager assets,
   74          AssetDesc<Dcc> asset,
   75          F handle,
   76          Object data
   77      ) {
   78        log.traceEntry("loadAsync(assets: {}, asset: {}, handle: {}, data: {})", assets, asset, handle, data);
   79        DcParams params = asset.params(DcParams.class);
   80        if (params.direction >= 0) {
   81          Dcc dcc = assets.getDepNow(AssetDesc.of(asset, PARENT_DC));
   82          assert data instanceof ByteBuf;
   83          ByteBuf buffer = (ByteBuf) data; // borrowed, don't release
   84          dcc.read(buffer, params.direction);
   85          DccDecoder decoder = decoders.obtain();
   86          try {
   87            decoder.decode(dcc, params.direction);
   88          } finally {
   89            decoders.release(decoder);
   90          }
   91          return dcc;
      ...
```
Post-state:
```java
   71    @Override
   72      protected <F extends FileHandle> Dcc loadAsync(
   73          AssetManager assets,
   74          AssetDesc<Dcc> asset,
   75          F handle,
   76          Object data
   77      ) {
   78        log.traceEntry("loadAsync(assets: {}, asset: {}, handle: {}, data: {})", assets, asset, handle, data);
   79        DcParams params = asset.params(DcParams.class);
   80        if (params.direction >= 0) {
   81          Dcc dcc = assets.getDepNow(AssetDesc.of(asset, PARENT_DC));
   82          assert data instanceof ByteBuf;
   83          ByteBuf buffer = (ByteBuf) data; // borrowed, don't release
   84          dcc.read(buffer, params.direction);
   85          DccDecoder decoder = decoders.obtain();
   86          try {
   87 >>         log.trace("decoding {}", asset);
   88            decoder.decode(dcc, params.direction);
   89          } finally {
   90            decoders.release(decoder);
   91          }
   92          return dcc;
   93        } else {
   94          assert data instanceof InputStream;
   95          InputStream stream = (InputStream) data;
   96          try {
   97            return Dcc.read(handle, stream);
   98          } finally {
   99            IOUtils.closeQuietly(stream);
  100          }
  101        }
  102      }
```

## Mindustry:8c3577c55abb:0 — ADD_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/8c3577c55abb21e0c278a8c395aa82811b7fa797
- method: `Fonts.getGlyph(Font,char)` in `core/src/mindustry/ui/Fonts.java`
- added statement (post-state): `Log.err("No glyph: " + glyph + " (" + (int)glyph + ")")`
- levels: None -> ERROR

Pre-state:
```java
  212    public static TextureRegionDrawable getGlyph(Font font, char glyph){
  213            Glyph g = font.getData().getGlyph(glyph);
  214            if(g == null) throw new IllegalArgumentException("No glyph: " + glyph + " (" + (int)glyph + ")");
  215    
  216            float size = Math.max(g.width, g.height);
  217            TextureRegionDrawable draw = new TextureRegionDrawable(new TextureRegion(font.getRegion().texture, g.u, g.v2, g.u2, g.v)){
  218                @Override
  219                public void draw(float x, float y, float width, float height){
  220                    Draw.color(Tmp.c1.set(tint).mul(Draw.getColor()).toFloatBits());
  221                    float cx = x + width/2f - g.width/2f, cy = y + height/2f - g.height/2f;
  222                    cx = (int)cx;
  223                    cy = (int)cy;
  224                    Draw.rect(region, cx + g.width/2f, cy + g.height/2f, g.width, g.height);
  225                }
  226    
  227                @Override
  228                public void draw(float x, float y, float originX, float originY, float width, float height, float scaleX, float scaleY, float rotation){
  229                    width *= scaleX;
  230                    height *= scaleY;
  231                    Draw.color(Tmp.c1.set(tint).mul(Draw.getColor()).toFloatBits());
  232                    float cx = x + width/2f - g.width/2f, cy = y + height/2f - g.height/2f;
      ...
```
Post-state:
```java
  212    public static TextureRegionDrawable getGlyph(Font font, char glyph){
  213            Glyph g = font.getData().getGlyph(glyph);
  214            if(g == null){
  215 >>             Log.err("No glyph: " + glyph + " (" + (int)glyph + ")");
  216                return new TextureRegionDrawable(Core.atlas.find("whiteui"));
  217            }
  218    
  219            float size = Math.max(g.width, g.height);
  220            TextureRegionDrawable draw = new TextureRegionDrawable(new TextureRegion(font.getRegion().texture, g.u, g.v2, g.u2, g.v)){
  221                @Override
  222                public void draw(float x, float y, float width, float height){
  223                    Draw.color(Tmp.c1.set(tint).mul(Draw.getColor()).toFloatBits());
  224                    float cx = x + width/2f - g.width/2f, cy = y + height/2f - g.height/2f;
  225                    cx = (int)cx;
  226                    cy = (int)cy;
  227                    Draw.rect(region, cx + g.width/2f, cy + g.height/2f, g.width, g.height);
  228                }
  229    
  230                @Override
  231                public void draw(float x, float y, float originX, float originY, float width, float height, float scaleX, float scaleY, float rotation){
  232                    width *= scaleX;
  233                    height *= scaleY;
  234                    Draw.color(Tmp.c1.set(tint).mul(Draw.getColor()).toFloatBits());
  235                    float cx = x + width/2f - g.width/2f, cy = y + height/2f - g.height/2f;
      ...
```

## subspace-infinity:5c6588d3e7ab:6 — ADD_LOG

- repo: subspace-infinity  commit: https://github.com/assofohdz/subspace-infinity/commit/5c6588d3e7ab192b8c4c894779db0939704569b5
- method: `GameServer.main(String)` in `infinity/src/main/java/infinity/server/GameServer.java`
- added statement (post-state): `log.error(String.format("Unknown command:%s", line))`
- levels: None -> ERROR

Pre-state:
```java
  458    public static void main(final String... args) throws Exception {
  459    
  460        final StringWriter sOut = new StringWriter();
  461        try (PrintWriter out = new PrintWriter(sOut)) {
  462          boolean hasDescription = false;
  463          for (int i = 0; i < args.length; i++) {
  464            if ("-m".equals(args[i])) {
  465              out.println(args[++i]);
  466              hasDescription = true;
  467            }
  468          }
  469          if (!hasDescription) {
  470            // Put a default description in
  471            out.println("Dedicated Server");
  472            out.println();
  473            out.println("In game:");
  474            out.println("WASD + mouse to move");
  475            out.println("Enter to open chat bar");
  476            out.println("F5 to toggle stats");
  477            out.println("Esc to open in-game help");
  478            out.println("PrtScrn to save a screen shot");
      ...
```
Post-state:
```java
      ...
  363            out.println("PrtScrn to save a screen shot");
  364          }
  365    
  366          out.flush();
  367          final String desc = sOut.toString();
  368    
  369          final GameServer gs = new GameServer(InfinityConstants.DEFAULT_PORT, desc);
  370          gs.start();
  371    
  372          final BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
  373          String line;
  374          while ((line = in.readLine()) != null) {
  375            if (line.length() == 0) {
  376              continue;
  377            }
  378            if ("exit".equals(line)) {
  379              break;
  380            } else if ("stats".equals(line)) {
  381              gs.logStats();
  382            } else {
  383 >>           log.error(String.format("Unknown command:%s", line));
  384            }
  385          }
  386          gs.close();
  387        }
  388      }
```

## OpenRTS:40e03e6dc990:12 — ADD_LOG

- repo: OpenRTS  commit: https://github.com/methusalah/OpenRTS/commit/40e03e6dc9902e3b5ab7b0ed3ac5088514bbcb78
- method: `MapFactory.load()` in `RTSForGit/src/model/map/MapFactory.java`
- added statement (post-state): `LogUtil.logger.info("Loading map "+f.getCanonicalPath()+"...")`
- levels: None -> INFO

Pre-state:
```java
   46    public Map load(){
   47            Map res = null;
   48            final JFileChooser fc = new JFileChooser("assets/maps");
   49            int returnVal = fc.showOpenDialog(null);
   50            if (returnVal==JFileChooser.APPROVE_OPTION) {
   51                    File f = fc.getSelectedFile();
   52                    try {
   53                        res = load(f);
   54                    } catch (Exception e1) {
   55                            e1.printStackTrace();
   56                    }
   57            }
   58            if(res == null){
   59                LogUtil.logger.info("Load failed");
   60                return null;
   61            }
   62            
   63            lib.getMapStyleBuilder(res.mapStyleID).build(res);
   64            linkTiles(res);
   65            
   66            for(Tile t : res.tiles)
      ...
```
Post-state:
```java
   53    public Map load(){
   54            Map res = null;
   55            final JFileChooser fc = new JFileChooser(Model.DEFAULT_MAP_PATH);
   56            int returnVal = fc.showOpenDialog(null);
   57            if (returnVal == JFileChooser.APPROVE_OPTION) {
   58                    File f = fc.getSelectedFile();
   59                    try {
   60 >>                     LogUtil.logger.info("Loading map "+f.getCanonicalPath()+"...");
   61                        res = load(f);
   62                    } catch (Exception e1) {
   63                            e1.printStackTrace();
   64                    }
   65            }
   66            if(res == null){
   67                LogUtil.logger.info("Load failed");
   68                return null;
   69            }
   70            
   71            LogUtil.logger.info("   builders");
   72            lib.getMapStyleBuilder(res.mapStyleID).build(res);
   73    
   74            LogUtil.logger.info("   tiles' links");
   75            linkTiles(res);
   76            
   77            for(Tile t : res.tiles)
   78                if(t.isCliff)
   79                    t.setCliff();
   80            
      ...
```

## OpenKeeper:3684145f5538:6 — ADD_LOG

- repo: OpenKeeper  commit: https://github.com/tonihele/OpenKeeper/commit/3684145f553823ffd9791b11d6e4ffd7d8490c3a
- method: `KwdFile.readCreatureSpells(KwdHeader,RandomAccessFile)` in `src/toniarts/opendungeonkeeper/tools/convert/map/KwdFile.java`
- added statement (post-state): `logger.info("Reading creature spells!")`
- levels: None -> INFO

Pre-state:
```java
 1323    private void readCreatureSpells(String dkIIPath) throws RuntimeException {
 1324    
 1325            // Read the creature spells catalog
 1326            File creatureSpellsFile = new File(dkIIPath.concat("Data").concat(File.separator).concat("editor").concat(File.separator).concat("CreatureSpells.kwd"));
 1327            try (RandomAccessFile rawCreatureSpells = new RandomAccessFile(creatureSpellsFile, "r")) {
 1328    
 1329                // Creature spells file has a 36 header
 1330                rawCreatureSpells.seek(20);
 1331                int creatureSpellsCount = Utils.readUnsignedInteger(rawCreatureSpells);
 1332    
 1333                // The creature spells file is just simple blocks until EOF
 1334                rawCreatureSpells.seek(36); // End of header
 1335                rawCreatureSpells.skipBytes(20); // I don't know what is in here
 1336    
 1337                creatureSpells = new ArrayList<>(creatureSpellsCount);
 1338                for (int i = 0; i < creatureSpellsCount; i++) {
 1339                    CreatureSpell creatureSpell = new CreatureSpell();
 1340                    byte[] bytes = new byte[32];
 1341                    rawCreatureSpells.read(bytes);
 1342                    creatureSpell.setName(Utils.bytesToString(bytes).trim());
 1343                    short[] data = new short[234];
      ...
```
Post-state:
```java
 1433    private void readCreatureSpells(KwdHeader header, RandomAccessFile file) throws IOException {
 1434    
 1435            // Read the creature spells catalog
 1436 >>         logger.info("Reading creature spells!");
 1437            creatureSpells = new ArrayList<>(header.getItemCount());
 1438            for (int i = 0; i < header.getItemCount(); i++) {
 1439                long offset = file.getFilePointer();
 1440                CreatureSpell creatureSpell = new CreatureSpell();
 1441                byte[] bytes = new byte[32];
 1442                file.read(bytes);
 1443                creatureSpell.setName(Utils.bytesToString(bytes).trim());
 1444                short[] data = new short[234];
 1445                for (int x = 0; x < data.length; x++) {
 1446                    data[x] = (short) file.readUnsignedByte();
 1447                }
 1448                creatureSpell.setData(data);
 1449    
 1450                // Add to the list
 1451                creatureSpells.add(creatureSpell);
 1452    
 1453                // Check file offset
 1454                checkOffset(header, file, offset);
 1455            }
 1456        }
```

## OpenRTS:86f681c3bb04:4 — ADD_LOG

- repo: OpenRTS  commit: https://github.com/methusalah/OpenRTS/commit/86f681c3bb04ed33cdeba83758e587b438a14b2b
- method: `EditorGUI.update()` in `RTSForGit/src/controller/editor/EditorGUI.java`
- added statement (post-state): `LogUtil.logger.info("updating editor gui but screen's not ready.")`
- levels: None -> INFO

Pre-state:
```java
   41    @Override
   42        public void update() {
   43            String n = System.getProperty("line.separator");
   44    
   45            // update unities
   46            unities = c.getUnitiesInContext();
   47            // Unity selectors
   48            for(int i=0; i<5; i++){
   49                if(i > unities.size()-1){
   50                    if(getElement("psel"+i).isVisible())
   51                        getElement("psel"+i).hide();
   52                } else {
   53                    if(!getElement("psel"+i).isVisible())
   54                        getElement("psel"+i).show();
   55                    if(getElement("sel"+i) != null && getElement("sel"+i).getRenderer(TextRenderer.class)!=null){
   56                        Unity u = unities.get(i);
   57                        getElement("sel"+i).getRenderer(TextRenderer.class).setText(u.get(0).UIName+n+u.size());
   58                    }
   59                }
   60            }
   61            
      ...
```
Post-state:
```java
   40    @Override
   41        public void update() {
   42            if(!nifty.getCurrentScreen().getScreenId().equals("editor")){
   43 >>             LogUtil.logger.info("updating editor gui but screen's not ready.");
   44                return;
   45            }
   46            if(toRefresh)
   47                refresh();
   48            
   49            String n = System.getProperty("line.separator");
   50            
   51    //        setText("operation2", "pointed : "+ctrl.model.toolManager.pointedSpatialLabel);
   52    
   53    //        // update unities
   54    //        unities = c.getUnitiesInContext();
   55    //        // Unity selectors
   56    //        for(int i=0; i<5; i++){
   57    //            if(i > unities.size()-1){
   58    //                if(getElement("psel"+i).isVisible())
   59    //                    getElement("psel"+i).hide();
   60    //            } else {
   61    //                if(!getElement("psel"+i).isVisible())
   62    //                    getElement("psel"+i).show();
   63    //                if(getElement("sel"+i) != null && getElement("sel"+i).getRenderer(TextRenderer.class)!=null){
      ...
```

## OpenRTS:21d19d044e66:2 — ADD_LOG

- repo: OpenRTS  commit: https://github.com/methusalah/OpenRTS/commit/21d19d044e66f07ecc50e91a83f78f3256346158
- method: `Dug1Ortho.extrudeProfile()` in `RTSForGit/src/model/map/cliff/faces/natural/Dug1Ortho.java`
- added statement (post-state): `LogUtil.logger.info("applied low = "+(v.z/Tile.STAGE_HEIGHT)*parentRampLow)`
- levels: None -> INFO

Pre-state:
```java
   26    @Override
   27        protected void extrudeProfile() {
   28            int i = 0;
   29            double ridgeDepth = MyRandom.between(1+RIDGE_PROTRUDE*ridgeDepthRange, 1-RIDGE_RETREAT*ridgeDepthRange);
   30            double ridgePos = MyRandom.between(1+MAX_RIDGE_POS*ridgePosRange, 1-MAX_RIDGE_POS*ridgePosRange);
   31            
   32            for(Point3D v : parentProfile)
   33                grid[0][i++] = v.getAddition(0, 1, 0);
   34            i = 0;
   35            for(Point3D v : middleProfile)
   36                grid[1][i++] = v.getAddition(0, 0.5*ridgePos, 0).get2D().getMult(ridgeDepth, 1).get3D(v.z);
   37            i = 0;
   38            for(Point3D v : childProfile)
   39                grid[2][i++] = v;
   40        }
```
Post-state:
```java
      ...
   50            double parentRampLow, childRampLow;
   51            if(cliff.parent == null){
   52                parentRampLow = -Tile.STAGE_HEIGHT;
   53                childRampLow = cliff.tile.getNeighbRampZ();
   54            } else if(cliff.parent.getNeighbRampZ() <= cliff.tile.getNeighbRampZ()){
   55                parentRampLow = cliff.parent.getNeighbRampZ();
   56                childRampLow = cliff.tile.getNeighbRampZ();
   57            } else {
   58                parentRampLow = cliff.tile.getNeighbRampZ();
   59                childRampLow = cliff.tile.getNeighbRampZ() - Tile.STAGE_HEIGHT/4;
   60            }
   61                
   62            
   63            
   64            for(Point3D v : parentProfile){
   65                grid[0][i++] = v.getAddition(0, 1, 0)
   66                        .getAddition(0, 0, (v.z/Tile.STAGE_HEIGHT)*parentRampLow);
   67                if(parentRampLow != 0){
   68                    LogUtil.logger.info("ramp low = "+parentRampLow);
   69                    LogUtil.logger.info("z           = "+v.z);
   70 >>                 LogUtil.logger.info("applied low = "+(v.z/Tile.STAGE_HEIGHT)*parentRampLow);
   71                }
   72            }
   73            i = 0;
   74            for(Point3D v : middleProfile)
   75                grid[1][i++] = v.getAddition(0, 0.5*ridgePos, 0).get2D().getMult(ridgeDepth, 1).get3D(v.z)
   76                        .getAddition(0, 0, (v.z/Tile.STAGE_HEIGHT)*(parentRampLow+childRampLow)/2);
   77            i = 0;
   78            for(Point3D v : childProfile)
   79                grid[2][i++] = v
   80                        .getAddition(0, 0, (v.z/Tile.STAGE_HEIGHT)*childRampLow);
   81        }
```

## Archer-Game-Template2:e4d8d3cc37a5:0 — ADD_LOG

- repo: Archer-Game-Template2  commit: https://github.com/capdevon/Archer-Game-Template2/commit/e4d8d3cc37a5702137bc87a2a725de24af17f42d
- method: `GInputAppState.mapJoystick(Joystick)` in `game/src/main/java/com/capdevon/input/GInputAppState.java`
- added statement (post-state): `logger.info("The joystick has Z axes.")`
- levels: None -> INFO

Pre-state:
```java
   44    @Override
   45        public void mapJoystick(Joystick joypad) {
   46    
   47        	// FIXME: joystick mapping doesn't work with jme3-lwjgl3 (to be investigated)
   48            if (joypad.getAxis(JoystickAxis.Z_ROTATION) != null && joypad.getAxis(JoystickAxis.Z_AXIS) != null) {
   49                // let the dpad be up and down
   50                assignAxis(joypad.getPovYAxis(), KeyMapping.SWITCH_AMMO, KeyMapping.SWITCH_AMMO);
   51            }
   52    
   53            assignButton(joypad, JoystickButton.BUTTON_0, KeyMapping.EMPTY);
   54            assignButton(joypad, JoystickButton.BUTTON_1, KeyMapping.TOGGLE_CROUCH);
   55            assignButton(joypad, JoystickButton.BUTTON_2, KeyMapping.EMPTY);
   56            assignButton(joypad, JoystickButton.BUTTON_4, KeyMapping.RUNNING);
   57            assignButton(joypad, JoystickButton.BUTTON_5, KeyMapping.EMPTY);
   58            assignButton(joypad, JoystickButton.BUTTON_6, KeyMapping.AIMING);
   59            assignButton(joypad, JoystickButton.BUTTON_7, KeyMapping.FIRE);
   60            assignButton(joypad, JoystickButton.BUTTON_8, KeyMapping.EMPTY);
   61            assignButton(joypad, JoystickButton.BUTTON_9, KeyMapping.EMPTY);
   62    
   63            // Use the (left) stick to move.
   64            JoystickAxis xAxis = joypad.getAxis(JoystickAxis.X_AXIS);
      ...
```
Post-state:
```java
   44    @Override
   45        public void mapJoystick(Joystick joypad) {
   46    
   47        	// FIXME: joystick mapping doesn't work with jme3-lwjgl3 (to be investigated)
   48            JoystickAxis zAxis = joypad.getAxis(JoystickAxis.Z_AXIS);
   49            JoystickAxis zRotation = joypad.getAxis(JoystickAxis.Z_ROTATION);
   50            if (zRotation != null && zAxis != null) {
   51 >>             logger.info("The joystick has Z axes.");
   52    
   53                // Let the dpad be up and down
   54                assignAxis(joypad.getPovYAxis(), KeyMapping.SWITCH_AMMO, KeyMapping.SWITCH_AMMO);
   55    
   56            } else {
   57                logger.info("The joystick does not have Z axes.");
   58            }
   59    
   60            assignButton(joypad, JoystickButton.BUTTON_0, KeyMapping.EMPTY);
   61            assignButton(joypad, JoystickButton.BUTTON_1, KeyMapping.TOGGLE_CROUCH);
   62            assignButton(joypad, JoystickButton.BUTTON_2, KeyMapping.EMPTY);
   63            assignButton(joypad, JoystickButton.BUTTON_4, KeyMapping.RUNNING);
   64            assignButton(joypad, JoystickButton.BUTTON_5, KeyMapping.EMPTY);
   65            assignButton(joypad, JoystickButton.BUTTON_6, KeyMapping.AIMING);
   66            assignButton(joypad, JoystickButton.BUTTON_7, KeyMapping.FIRE);
   67            assignButton(joypad, JoystickButton.BUTTON_8, KeyMapping.EMPTY);
   68            assignButton(joypad, JoystickButton.BUTTON_9, KeyMapping.EMPTY);
   69    
   70            // Use the (left) stick to move.
   71            JoystickAxis xAxis = joypad.getAxis(JoystickAxis.X_AXIS);
      ...
```

## Mindustry:3562a706693e:1 — ADD_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/3562a706693e0ff07f7a5a59141528603be64750
- method: `NetClient.NetClient()` in `core/src/io/anuke/mindustry/core/NetClient.java`
- added statement (post-state): `Log.info("Recieved enemy {0}", spawn.id)`
- levels: None -> INFO

Pre-state:
```java
   51    public NetClient(){
   52    
   53            Net.handleClient(Connect.class, packet -> {
   54                Net.setClientLoaded(false);
   55                recieved.clear();
   56                dead.clear();
   57                connecting = true;
   58                gotData = false;
   59                kicked = false;
   60    
   61                ui.loadfrag.hide();
   62                ui.loadfrag.show("$text.connecting.data");
   63    
   64                Entities.clear();
   65    
   66                ConnectPacket c = new ConnectPacket();
   67                c.name = player.name;
   68                c.android = android;
   69                Net.send(c, SendMode.tcp);
   70    
   71                Timers.runTask(dataTimeout, () -> {
      ...
```
Post-state:
```java
      ...
  162            });
  163    
  164            Net.handleClient(EnemySpawnPacket.class, spawn -> {
  165                //duplicates.
  166                if (enemyGroup.getByID(spawn.id) != null ||
  167                        recieved.contains(spawn.id) || dead.contains(spawn.id)) return;
  168    
  169                recieved.add(spawn.id);
  170    
  171                Enemy enemy = new Enemy(EnemyType.getByID(spawn.type));
  172                enemy.interpolator.target.set(spawn.x, spawn.y);
  173                enemy.set(spawn.x, spawn.y);
  174                enemy.tier = spawn.tier;
  175                enemy.lane = spawn.lane;
  176                enemy.id = spawn.id;
  177                enemy.health = spawn.health;
  178                enemy.add();
  179    
  180                Effects.effect(Fx.spawn, enemy);
  181    
  182 >>             Log.info("Recieved enemy {0}", spawn.id);
  183            });
  184    
  185            Net.handleClient(EnemyDeathPacket.class, spawn -> {
  186                Enemy enemy = enemyGroup.getByID(spawn.id);
  187                if (enemy != null) enemy.onDeath();
  188                dead.add(spawn.id);
  189            });
  190    
  191            Net.handleClient(BulletPacket.class, packet -> {
  192                //TODO shoot effects for enemies, clientside as well as serverside
  193                BulletType type = (BulletType) BaseBulletType.getByID(packet.type);
  194                Entity owner = enemyGroup.getByID(packet.owner);
  195                new Bullet(type, owner, packet.x, packet.y, packet.angle).add();
  196            });
  197    
  198            Net.handleClient(BlockDestroyPacket.class, packet -> {
  199                Tile tile = world.tile(packet.position % world.width(), packet.position / world.width());
  200                if (tile != null && tile.entity != null) {
  201                    tile.entity.onDeath(true);
  202                }
      ...
```

## Mindustry:7ec3ab5a171a:1 — ADD_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/7ec3ab5a171a2ec6effa43816cd84c9e71b13731
- method: `.loadServers()` in `core/src/mindustry/ui/dialogs/JoinDialog.java`
- added statement (post-state): `Log.err(e)`
- levels: None -> ERROR

Pre-state:
```java
  506    @SuppressWarnings("unchecked")
  507        private void loadServers(){
  508            servers = Core.settings.getJson("servers", Seq.class, Server.class, Seq::new);
  509    
  510            //load imported legacy data
  511            if(Core.settings.has("server-list")){
  512                servers = LegacyIO.readServers();
  513                Core.settings.remove("server-list");
  514            }
  515    
  516            var url = becontrol.active() ? serverJsonBeURL : serverJsonV6URL;
  517            Log.info("Fetching community servers at @", url);
  518    
  519            //get servers
  520            Core.net.httpGet(url, result -> {
  521                try{
  522                    if(result.getStatus() != HttpStatus.OK){
  523                        Log.warn("Failed to fetch community servers: @", result.getStatus());
  524                        return;
  525                    }
  526    
      ...
```
Post-state:
```java
      ...
  529                        try{
  530                            defaultServers.clear();
  531                            val.asArray().each(child -> {
  532                                String name = child.getString("name", "");
  533                                String[] addresses;
  534                                if(child.has("addresses") || (child.has("address") && child.get("address").isArray())){
  535                                    addresses = (child.has("addresses") ? child.get("addresses") : child.get("address")).asArray().map(Jval::asString).toArray(String.class);
  536                                }else{
  537                                    addresses = new String[]{child.getString("address", "<invalid>")};
  538                                }
  539                                defaultServers.add(new ServerGroup(name, addresses));
  540                            });
  541                            Log.info("Fetched @ community servers.", defaultServers.size);
  542                        }catch(Throwable e){
  543                            Log.err("Failed to parse community servers.");
  544                            Log.err(e);
  545                        }
  546                    });
  547                }catch(Throwable e){
  548                    Log.err("Failed to fetch community servers.");
  549 >>                 Log.err(e);
  550                }
  551            }, Log::err);
  552        }
```

## Mindustry:9f7817f70e08:1 — ADD_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/9f7817f70e0864f8a59b92d72af554fc244df9ff
- method: `ContentPatcher.unapply()` in `core/src/mindustry/mod/ContentPatcher.java`
- added statement (post-state): `Log.err("Failed to un-apply patch!", e)`
- levels: None -> ERROR

Pre-state:
```java
   49    public void unapply() throws Exception{
   50            if(!applied) return;
   51    
   52            Vars.content = contentLoader;
   53            applied = false;
   54    
   55            resetters.reverse();
   56            resetters.each(Runnable::run);
   57            resetters.clear();
   58    
   59            afterCallbacks.each(Runnable::run);
   60            afterCallbacks.clear();
   61        }
```
Post-state:
```java
   53    public void unapply(){
   54            if(!applied) return;
   55    
   56            Vars.content = contentLoader;
   57            applied = false;
   58    
   59            resetters.reverse();
   60            for(var reset : resetters){
   61                try{
   62                    reset.run();
   63                }catch(Throwable e){
   64 >>                 Log.err("Failed to un-apply patch!", e);
   65                }
   66            }
   67            resetters.clear();
   68    
   69            //this should never throw an exception
   70            afterCallbacks.each(Runnable::run);
   71            afterCallbacks.clear();
   72        }
```

## OpenKeeper:5dc468ade607:0 — ADD_LOG

- repo: OpenKeeper  commit: https://github.com/tonihele/OpenKeeper/commit/5dc468ade607d687b8814c904a4974d71cb3841c
- method: `MapViewController.setRandomTexture(Spatial,MapTile)` in `src/toniarts/openkeeper/view/map/MapViewController.java`
- added statement (post-state): `LOGGER.log(Level.WARNING, "Failed to load a random texture to terrain id " + tile.getTerrainId() + ", texture index " + tex + "!", e)`
- levels: None -> WARN

Pre-state:
```java
  419    private void setRandomTexture(final Spatial spatial, final MapTile tile) {
  420    
  421            // Check the data on geometry, basically we could allow the players to play with different skins
  422            spatial.depthFirstTraversal(new SceneGraphVisitor() {
  423                @Override
  424                public void visit(Spatial spatial) {
  425                    Integer texCount = spatial.getUserData(KmfModelLoader.MATERIAL_ALTERNATIVE_TEXTURES_COUNT);
  426                    if (texCount != null) {
  427    
  428                        // On redrawing, see if we already randomized this
  429                        // The principle is bit wrong, the random texture is tied to the tile, and not material etc.
  430                        // But it is probably just the tops of few tiles, so...
  431                        int tex;
  432                        if (tile.getRandomTextureIndex() != null) {
  433                            tex = tile.getRandomTextureIndex();
  434    
  435                            // FIXME: Rock top fails, we may have a problem in the material naming
  436                            if (texCount >= tex) {
  437                                tex = texCount - 1;
  438                            }
  439                        } else {
      ...
```
Post-state:
```java
      ...
  425                    Integer texCount = spatial.getUserData(KmfModelLoader.MATERIAL_ALTERNATIVE_TEXTURES_COUNT);
  426                    if (texCount != null) {
  427    
  428                        // The principle is bit wrong, the random texture is tied to the tile, and not material etc.
  429                        // But it is probably just the tops of few tiles, so...
  430                        int tex = tile.getRandomTextureIndex();
  431                        if (tex != 0) { // 0 is the default anyway
  432                            Geometry g = (Geometry) spatial;
  433                            Material m = g.getMaterial();
  434                            String asset = m.getAssetName();
  435    
  436                            // Load new material
  437                            try {
  438                                Material newMaterial = assetManager.loadMaterial(asset.substring(0,
  439                                        asset.lastIndexOf(KmfModelLoader.MATERIAL_ALTERNATIVE_TEXTURE_SUFFIX_SEPARATOR) + 1).concat(tex + ".j3m"));
  440                                AssetUtils.assignMapsToMaterial(assetManager, newMaterial);
  441                                g.setMaterial(newMaterial);
  442                            } catch (Exception e) {
  443    
  444                                // FIXME: Rock top fails, we may have a problem in the material naming
  445 >>                             LOGGER.log(Level.WARNING, "Failed to load a random texture to terrain id " + tile.getTerrainId() + ", texture index " + tex + "!", e);
  446                            }
  447    
  448                        }
  449                    }
  450                }
  451            });
  452        }
```

## riiablo:31af776e42a1:0 — ADD_LOG

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/31af776e42a1f7bfceafe56de4b163b84e14061e
- method: `EndpointedChannelHandler.exceptionCaught(ChannelHandlerContext,Throwable)` in `core/src/com/riiablo/net/EndpointedChannelHandler.java`
- added statement (post-state): `Gdx.app.error(TAG, cause.getMessage(), cause)`
- levels: None -> ERROR

Pre-state:
```java
   68    @Override
   69      public void exceptionCaught(ChannelHandlerContext ctx, Throwable cause) throws Exception {
   70        if (DEBUG_CALLS) Gdx.app.debug(TAG, "exceptionCaught");
   71        ctx.fireExceptionCaught(cause);
   72      }
```
Post-state:
```java
   68    @Override
   69      public void exceptionCaught(ChannelHandlerContext ctx, Throwable cause) throws Exception {
   70        if (DEBUG_CALLS) Gdx.app.debug(TAG, "exceptionCaught");
   71 >>     Gdx.app.error(TAG, cause.getMessage(), cause);
   72        ctx.close();
   73      }
```

## Mindustry:27c4210482ae:0 — ADD_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/27c4210482aedd56fd6cb264dbde99d2fbb47643
- method: `Planet.init()` in `core/src/mindustry/type/Planet.java`
- added statement (post-state): `Log.err(e)`
- levels: None -> ERROR

Pre-state:
```java
  361    @Override
  362        public void init(){
  363            applyDefaultRules(campaignRules);
  364            loadRules();
  365    
  366            if(techTree == null){
  367                techTree = TechTree.roots.find(n -> n.planet == this);
  368            }
  369    
  370            if(techTree != null && autoAssignPlanet){
  371                techTree.addDatabaseTab(this);
  372                techTree.addPlanet(this);
  373            }
  374    
  375            for(Sector sector : sectors){
  376                sector.loadInfo();
  377            }
  378    
  379            if(generator != null){
  380                Noise.setSeed(sectorSeed < 0 ? id + 1 : sectorSeed);
  381    
      ...
```
Post-state:
```java
      ...
  373            if(techTree != null && autoAssignPlanet){
  374                techTree.addDatabaseTab(this);
  375                techTree.addPlanet(this);
  376            }
  377    
  378            for(Sector sector : sectors){
  379                sector.loadInfo();
  380            }
  381    
  382            if(generator != null){
  383                Noise.setSeed(sectorSeed < 0 ? id + 1 : sectorSeed);
  384    
  385                for(Sector sector : sectors){
  386                    generator.generateSector(sector);
  387                }
  388    
  389                if(attackSectorBitString != null){
  390                    try{
  391                        loadAttackBits(attackSectorBitString);
  392                    }catch(Exception e){
  393 >>                     Log.err(e);
  394                    }
  395                }
  396    
  397                updateBaseCoverage();
  398            }
  399    
  400            clipRadius = Math.max(clipRadius, radius + atmosphereRadOut + 0.5f);
  401        }
```

## Mindustry:565b79d1b28b:0 — ADD_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/565b79d1b28bbc0c95836f59447e95620d42330a
- method: `SWorkshop.onUnsubscribeItem(SteamPublishedFileID,SteamResult)` in `desktop/src/io/anuke/mindustry/desktop/steam/SWorkshop.java`
- added statement (post-state): `Log.info("Item unsubscribed from {0}", info.getFolder())`
- levels: None -> INFO

Pre-state:
```java
   36    @Override
   37        public void onUnsubscribeItem(SteamPublishedFileID publishedFileID, SteamResult result){
   38    
   39        }
```
Post-state:
```java
   36    @Override
   37        public void onUnsubscribeItem(SteamPublishedFileID publishedFileID, SteamResult result){
   38            ItemInstallInfo info = new ItemInstallInfo();
   39            ugc.getItemInstallInfo(publishedFileID, info);
   40 >>         Log.info("Item unsubscribed from {0}", info.getFolder());
   41        }
```

## subspace-infinity:8283ec8c3c64:32 — ADD_LOG

- repo: subspace-infinity  commit: https://github.com/assofohdz/subspace-infinity/commit/8283ec8c3c64a578c3a479684ab93a2f9a802fb5
- method: `ModelViewState.MarkVisible.update()` in `infinity/src/main/java/infinity/client/view/ModelViewState.java`
- added statement (post-state): `log.info("Marking static object visible:" + model.entityId)`
- levels: None -> INFO

Pre-state:
```java
  636    public void update() {
  637                // log.info("MarkVisible.update() useCount:" + model.useCount + " dynamic:" +
  638                // model.dynamic);
  639                // If the model is still static in some way then
  640                // we'll mark for static visibility
  641                if (model.useCount == 1 && model.dynamic) {
  642                    log.info("only dynamic... should already be visible.");
  643                    // Somehow it's only dynamic... no spawn position at all
  644                    return;
  645                }
  646                if (model.useCount == 0) {
  647                    // Model is no longer in use
  648                    log.info("not used anymore");
  649                    return;
  650                }
  651    
  652                // log.info("Marking static object visible:" + model.entityId);
  653                // Should be safe to add our static visibility marker
  654                model.markVisible();
  655            }
```
Post-state:
```java
  735    public void update() {
  736                log.info("MarkVisible.update() useCount:" + model.useCount + "  dynamic:" + model.dynamic);
  737                // If the model is still static in some way then
  738                // we'll mark for static visibility
  739                if( model.useCount == 1 && model.dynamic ) {
  740                    log.info("only dynamic... should already be visible.");
  741                    // Somehow it's only dynamic... no spawn position at all
  742                    return;
  743                }
  744                if( model.useCount == 0 ) {
  745                    // Model is no longer in use
  746                    log.info("not used anymore");
  747                    return;
  748                }
  749    
  750 >>             log.info("Marking static object visible:" + model.entityId);
  751                // Should be safe to add our static visibility marker
  752                model.markVisible();
  753            }
```

## OpenRTS:e12d2b2e81a3:2 — ADD_LOG

- repo: OpenRTS  commit: https://github.com/methusalah/OpenRTS/commit/e12d2b2e81a395538588ba0bb4583ab8e9be4680
- method: `MapView.reset()` in `core/src/view/MapView.java`
- added statement (post-state): `LogUtil.logger.info("reset")`
- levels: None -> INFO

Pre-state:
```java
   61    public void reset() {
   62    		// Light drawer
   63    		lightDrawer.reset();
   64    		ModelManager.getBattlefield().getSunLight().addListener(lightDrawer);
   65    		
   66    		// map drawer
   67    		if(mapDrawer != null){
   68    			rootNode.detachChild(mapDrawer.mainNode);
   69    			EventManager.unregister(mapDrawer);
   70    		}
   71    		mapDrawer = new MapDrawer(this, materialManager, assetManager);
   72    		rootNode.attachChild(mapDrawer.mainNode);
   73    		mapDrawer.mainPhysicsSpace = physicsSpace;
   74    			
   75    		// actor drawer
   76    		if(actorDrawer != null){
   77    			rootNode.detachChild(actorDrawer.mainNode);
   78    		}
   79    		actorDrawer = new ActorDrawer(assetManager, materialManager);
   80    		rootNode.attachChild(actorDrawer.mainNode);
   81    		actorDrawer.mainPhysicsSpace = physicsSpace;
      ...
```
Post-state:
```java
   61    public void reset() {
   62 >> 		LogUtil.logger.info("reset");
   63    		// Light drawer
   64    		lightDrawer.reset();
   65    		ModelManager.getBattlefield().getSunLight().addListener(lightDrawer);
   66    		
   67    		// map drawer
   68    		if(mapDrawer != null){
   69    			rootNode.detachChild(mapDrawer.mainNode);
   70    			EventManager.unregister(mapDrawer);
   71    		}
   72    		mapDrawer = new MapDrawer(this, materialManager, assetManager);
   73    		rootNode.attachChild(mapDrawer.mainNode);
   74    		mapDrawer.mainPhysicsSpace = physicsSpace;
   75    			
   76    		// actor drawer
   77    		if(actorDrawer != null){
   78    			rootNode.detachChild(actorDrawer.mainNode);
   79    		}
   80    		actorDrawer = new ActorDrawer(assetManager, materialManager);
   81    		rootNode.attachChild(actorDrawer.mainNode);
   82    		actorDrawer.mainPhysicsSpace = physicsSpace;
      ...
```

## OpenKeeper:d1406a8d4afa:1 — ADD_LOG

- repo: OpenKeeper  commit: https://github.com/tonihele/OpenKeeper/commit/d1406a8d4afad1959d306c26d8a0972c8458b755
- method: `KwdFile.readArtResource(RandomAccessFile)` in `src/toniarts/openkeeper/tools/convert/map/KwdFile.java`
- added statement (post-state): `logger.log(Level.WARNING, "Unknown artResource type {0}", type)`
- levels: None -> WARN

Pre-state:
```java
  625    private ArtResource readArtResource(RandomAccessFile file) throws IOException {
  626            ArtResource artResource = new ArtResource();
  627    
  628            // Read the data
  629            artResource.setName(ConversionUtils.bytesToString(file, 64).trim());
  630            long flags = ConversionUtils.readUnsignedIntegerAsLong(file);
  631            byte[] bytes = new byte[12];
  632            file.read(bytes); // Depends on the type how these are interpreted?
  633            short type = (short) file.readUnsignedByte();
  634            short startAf = (short) file.readUnsignedByte();
  635            short endAf = (short) file.readUnsignedByte();
  636            short sometimesOne = (short) file.readUnsignedByte();
  637    
  638            // Debug
  639            // System.out.println("Name: " + artResource.getName());
  640            // System.out.println("Type: " + type);
  641            // System.out.println("Flag: " + flags);
  642    
  643            // Mesh collection (type 8) has just the name, reference to GROP meshes probably
  644            // And alphas and images probably share the same attributes
  645            ResourceType resourceType = artResource.new ResourceType();
      ...
```
Post-state:
```java
      ...
  672                    ((Mesh) resourceType).setScale(ConversionUtils.readUnsignedInteger(Arrays.copyOfRange(bytes, 0, 4)) / ConversionUtils.FLOAT);
  673                    ((Mesh) resourceType).setFrames(ConversionUtils.readUnsignedShort(Arrays.copyOfRange(bytes, 4, 6)));
  674                    break;
  675                }
  676                case 6: {
  677                    resourceType = artResource.new Animation();
  678                    ((Animation) resourceType).setFrames(ConversionUtils.readUnsignedInteger(Arrays.copyOfRange(bytes, 0, 4)));
  679                    ((Animation) resourceType).setFps(ConversionUtils.readUnsignedInteger(Arrays.copyOfRange(bytes, 4, 8)));
  680                    ((Animation) resourceType).setStartDist(ConversionUtils.readUnsignedShort(Arrays.copyOfRange(bytes, 8, 10)));
  681                    ((Animation) resourceType).setEndDist(ConversionUtils.readUnsignedShort(Arrays.copyOfRange(bytes, 10, 12)));
  682                    break;
  683                }
  684                case 7: {
  685                    resourceType = artResource.new Proc();
  686                    ((Proc) resourceType).setId(ConversionUtils.readUnsignedInteger(Arrays.copyOfRange(bytes, 0, 4)));
  687                    break;
  688    
  689    
  690                }
  691                default:
  692 >>                 logger.log(Level.WARNING, "Unknown artResource type {0}", type);
  693                    break;
  694            }
  695    
  696            // Add the common values
  697            resourceType.setFlags(ConversionUtils.parseFlagValue(flags, ArtResource.ArtResourceFlag.class));
  698            resourceType.setType(ConversionUtils.parseEnum(type, ArtResource.Type.class));
  699            resourceType.setStartAf(startAf);
  700    
  701            resourceType.setEndAf(endAf);
  702    
  703            resourceType.setSometimesOne(sometimesOne);
  704    
  705            artResource.setSettings(resourceType);
  706    
  707            // If it has no name or the type is not known, return null
  708            if (artResource.getName().isEmpty() || resourceType.getType() == null) {
  709                return null;
  710            }
  711    
  712            return artResource;
      ...
```

## Mindustry:134fea445c60:1 — REMOVE_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/134fea445c60cbce3087d31258e6806ee167daf3
- method: `ServerControl.ServerControl(String[])` in `server/src/io/anuke/mindustry/server/ServerControl.java`
- removed statement (pre-state): `Log.err("No suitable map found.")`
- levels: ERROR -> None

Pre-state:
```java
      ...
  150                if(Core.settings.getBool("shuffle")){
  151                    if(maps.all().size > 0){
  152                        Array<Map> maps = Array.with(Vars.maps.customMaps().size == 0 ? Vars.maps.defaultMaps() : Vars.maps.customMaps());
  153                        maps.shuffle();
  154    
  155                        Map previous = world.getMap();
  156                        Map map = maps.find(m -> m != previous || maps.size == 1);
  157    
  158                        if(map != null){
  159    
  160                            Call.onInfoMessage((state.rules.pvp
  161                            ? "[YELLOW]The " + event.winner.name() + " team is victorious![]" : "[SCARLET]Game over![]")
  162                            + "\nNext selected map:[accent] " + map.name() + "[]"
  163                            + (map.tags.containsKey("author") && !map.tags.get("author").trim().isEmpty() ? " by[accent] " + map.author() + "[]" : "") + "." +
  164                            "\nNew game begins in " + roundExtraTime + "[] seconds.");
  165    
  166                            info("Selected next map to be {0}.", map.name());
  167    
  168                            play(true, () -> world.loadMap(map, map.applyRules(lastMode)));
  169                        }else{
  170 >>                         Log.err("No suitable map found.");
  171                        }
  172                    }
  173                }else{
  174                    netServer.kickAll(KickReason.gameover);
  175                    state.set(State.menu);
  176                    net.closeServer();
  177                }
  178            });
  179    
  180            if(!mods.all().isEmpty()){
  181                info("&lc{0} mods loaded.", mods.all().size);
  182            }
  183    
  184            info("&lcServer loaded. Type &ly'help'&lc for help.");
  185            System.out.print("> ");
  186    
  187            if(Core.settings.getBool("socket")){
  188                toggleSocket(true);
  189            }
  190        }
```
Post-state:
```java
   58    public ServerControl(String[] args){
   59            Core.settings.defaults(
   60                "shufflemode", "normal",
   61                "bans", "",
   62                "admins", "",
   63                "shufflemode", "all",
   64                "crashreport", false,
   65                "port", port,
   66                "logging", true,
   67                "socket", false,
   68                "globalrules", "{reactorExplosions: false}"
   69            );
   70    
   71            Log.setLogger(new LogHandler(){
   72                DateTimeFormatter dateTime = DateTimeFormatter.ofPattern("MM-dd-yyyy | HH:mm:ss");
   73    
   74                @Override
   75                public void debug(String text, Object... args){
   76                    print("&lc&fb" + "[DEBG] " + text, args);
   77                }
   78    
      ...
```

## Mindustry:be60a367e818:0 — REMOVE_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/be60a367e8180b3afa4a2f2e3e58c8d367405e0b
- method: `AndroidLauncher.onCreate(Bundle)` in `android/src/io/anuke/mindustry/AndroidLauncher.java`
- removed statement (pre-state): `Log.e("SecurityException", "Google Play Services not available.")`
- levels: ERROR -> None

Pre-state:
```java
      ...
  108                    setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE);
  109                }
  110    
  111                @Override
  112                public void endForceLandscape(){
  113                    setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_SENSOR);
  114                }
  115    
  116                @Override
  117                public boolean canDonate(){
  118                    return true;
  119                }
  120            };
  121    
  122            try{
  123                ProviderInstaller.installIfNeeded(this);
  124            }catch(GooglePlayServicesRepairableException e){
  125                GoogleApiAvailability apiAvailability = GoogleApiAvailability.getInstance();
  126                apiAvailability.getErrorDialog(this, e.getConnectionStatusCode(), 0).show();
  127            }catch(GooglePlayServicesNotAvailableException e){
  128 >>             Log.e("SecurityException", "Google Play Services not available.");
  129            }
  130            if(doubleScaleTablets && isTablet(this.getContext())){
  131                Unit.dp.addition = 0.5f;
  132            }
  133            config.hideStatusBar = true;
  134            Net.setClientProvider(new KryoClient());
  135            Net.setServerProvider(new KryoServer());
  136            initialize(new Mindustry(), config);
  137            checkFiles(getIntent());
  138        }
```
Post-state:
```java
   42    @Override
   43        protected void onCreate(Bundle savedInstanceState){
   44            super.onCreate(savedInstanceState);
   45            AndroidApplicationConfiguration config = new AndroidApplicationConfiguration();
   46            config.useImmersiveMode = true;
   47            config.depth = 0;
   48            Platform.instance = new Platform(){
   49    
   50                @Override
   51                public void hide(){
   52                    moveTaskToBack(true);
   53                }
   54    
   55                @Override
   56                public String getUUID(){
   57                    try{
   58                        String s = Secure.getString(getContext().getContentResolver(), Secure.ANDROID_ID);
   59                        int len = s.length();
   60                        byte[] data = new byte[len / 2];
   61                        for(int i = 0; i < len; i += 2){
   62                            data[i / 2] = (byte) ((Character.digit(s.charAt(i), 16) << 4)
      ...
```

## Mindustry:01f4a9b23b98:9 — REMOVE_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/01f4a9b23b98ace924231cef29e167d53a56f78f
- method: `NetServer.NetServer()` in `core/src/io/anuke/mindustry/core/NetServer.java`
- removed statement (pre-state): `Log.info("&lc{0} has kicked {1}.", player.name, other.name)`
- levels: INFO -> None

Pre-state:
```java
      ...
  331                    Log.err("ACCESS DENIED: Player {0} / {1} attempted to perform admin action without proper security access.",
  332                            player.name, Net.getConnection(player.clientid).address);
  333                    return;
  334                }
  335    
  336                Player other = playerGroup.getByID(packet.id);
  337    
  338                if(other == null || other.isAdmin){
  339                    Log.err("{0} attempted to perform admin action on nonexistant or admin player.", player.name);
  340                    return;
  341                }
  342    
  343                String ip = Net.getConnection(other.clientid).address;
  344    
  345                if(packet.action == AdminAction.ban){
  346                    admins.banPlayerIP(ip);
  347                    kick(other.clientid, KickReason.banned);
  348                    Log.info("&lc{0} has banned {1}.", player.name, other.name);
  349                }else if(packet.action == AdminAction.kick){
  350                    kick(other.clientid, KickReason.kick);
  351 >>                 Log.info("&lc{0} has kicked {1}.", player.name, other.name);
  352                }else if(packet.action == AdminAction.trace){
  353                    TracePacket trace = new TracePacket();
  354                    trace.info = admins.getTraceByID(getUUID(id));
  355                    Net.sendTo(id, trace, SendMode.tcp);
  356                    Log.info("&lc{0} has requested trace info of {1}.", player.name, other.name);
  357                }
  358            });
  359    
  360            Net.handleServer(BlockLogRequestPacket.class, (id, packet) -> {
  361                packet.editlogs = admins.getEditLogs().get(packet.x + packet.y * world.width(), new Array<>());
  362                Net.sendTo(id, packet, SendMode.udp);
  363            });
  364    
  365            Net.handleServer(RollbackRequestPacket.class, (id, packet) -> {
  366                Player player = connections.get(id);
  367    
  368                if(!player.isAdmin){
  369                    Log.err("ACCESS DENIED: Player {0} / {1} attempted to perform a rollback without proper security access.",
  370                            player.name, Net.getConnection(player.clientid).address);
  371                    return;
      ...
```
Post-state:
```java
   38    public NetServer(){
   39    
   40            Net.handleServer(Connect.class, (id, connect) -> {
   41                if(admins.isIPBanned(connect.addressTCP)){
   42                    kick(id, KickReason.banned);
   43                }
   44            });
   45    
   46            Net.handleServer(ClientSnapshotPacket.class, (id, packet) -> {
   47                //...don't do anything here as it's already handled by the packet itself
   48            });
   49    
   50            Net.handleServer(InvokePacket.class, (id, packet) -> {
   51                //TODO implement
   52                //CallServer.readPacket(packet.writeBuffer, packet.type, connections.get(id));
   53            });
   54        }
```

## Mindustry:8850a89e301a:0 — REMOVE_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/8850a89e301af958a339c0b4b524fd177447233e
- method: `ServerControl.ServerControl(String[])` in `server/src/io/anuke/mindustry/server/ServerControl.java`
- removed statement (pre-state): `info("Two consecutive game-overs detected, shifting sector Y.")`
- levels: INFO -> None

Pre-state:
```java
      ...
   92                if(mode != ShuffleMode.off){
   93                    if(world.getSector() == null){
   94                        if(world.maps().all().size > 0){
   95                            Array<Map> maps = mode == ShuffleMode.both ? world.maps().all() :
   96                            mode == ShuffleMode.normal ? world.maps().defaultMaps() : world.maps().customMaps();
   97    
   98                            Map previous = world.getMap();
   99                            Map map = previous;
  100                            if(maps.size > 1){
  101                                while(map == previous) map = maps.random();
  102                            }
  103    
  104                            info("Selected next map to be {0}.", map.name);
  105    
  106                            logic.reset();
  107                            world.loadMap(map);
  108                            state.set(State.playing);
  109                        }
  110                    }else{
  111                        if(gameOvers >= 2){
  112 >>                         info("Two consecutive game-overs detected, shifting sector Y.");
  113                            Settings.putInt("sector_x", Settings.getInt("sector_x") - 1);
  114                            Settings.putInt("sector_y", Settings.getInt("sector_y") + 1);
  115                            Settings.save();
  116                        }
  117                        info("Re-trying sector map: {0} {1}",  Settings.getInt("sector_x"), Settings.getInt("sector_y"));
  118                        gameOvers ++;
  119                        playSectorMap();
  120                    }
  121                }else{
  122                    state.set(State.menu);
  123                    Net.closeServer();
  124                }
  125            });
  126    
  127            info("&lcServer loaded. Type &ly'help'&lc for help.");
  128        }
```
Post-state:
```java
   44    public ServerControl(String[] args){
   45            Settings.defaultList(
   46                "shufflemode", "normal",
   47                "bans", "",
   48                "admins", "",
   49                "sector_x", 0,
   50                "sector_y", 1
   51            );
   52    
   53            mode = ShuffleMode.valueOf(Settings.getString("shufflemode"));
   54    
   55            Effects.setScreenShakeProvider((a, b) -> {});
   56            Effects.setEffectProvider((a, b, c, d, e, f) -> {});
   57            Sounds.setHeadless(true);
   58    
   59            registerCommands();
   60    
   61            Gdx.app.postRunnable(() -> {
   62                String[] commands = {};
   63    
   64                if(args.length > 0){
      ...
```

## Mindustry:205c4e723ab2:0 — REMOVE_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/205c4e723ab2796480d5b3c401eeabf2c1644832
- method: `NetServer.NetServer()` in `core/src/io/anuke/mindustry/core/NetServer.java`
- removed statement (pre-state): `UCore.log("Connection found: " + connect.addressTCP)`
- levels: INFO -> None

Pre-state:
```java
   42    public NetServer(){
   43    
   44 >>         Net.handleServer(Connect.class, (id, connect) -> UCore.log("Connection found: " + connect.addressTCP));
   45    
   46            Net.handleServer(ConnectPacket.class, (id, packet) -> {
   47    
   48                if(packet.version != Net.version){
   49                    Net.kickConnection(id, packet.version > Net.version ? KickReason.serverOutdated : KickReason.clientOutdated);
   50                    return;
   51                }
   52    
   53                UCore.log("Sending world data to client (ID=" + id + ")");
   54    
   55                Player player = new Player();
   56                player.clientid = id;
   57                player.name = packet.name;
   58                player.isAndroid = packet.android;
   59                player.set(world.getSpawnX(), world.getSpawnY());
   60                player.interpolator.last.set(player.x, player.y);
   61                player.interpolator.target.set(player.x, player.y);
   62                connections.put(id, player);
   63    
   64                if(world.getMap().custom){
      ...
```
Post-state:
```java
   42    public NetServer(){
   43    
   44            Net.handleServer(Connect.class, (id, connect) -> {});
   45    
   46            Net.handleServer(ConnectPacket.class, (id, packet) -> {
   47    
   48                if(packet.version != Net.version){
   49                    Net.kickConnection(id, packet.version > Net.version ? KickReason.serverOutdated : KickReason.clientOutdated);
   50                    return;
   51                }
   52    
   53                Log.info("Sending world data to client (ID = {0})", id);
   54    
   55                Player player = new Player();
   56                player.clientid = id;
   57                player.name = packet.name;
   58                player.isAndroid = packet.android;
   59                player.set(world.getSpawnX(), world.getSpawnY());
   60                player.interpolator.last.set(player.x, player.y);
   61                player.interpolator.target.set(player.x, player.y);
   62                connections.put(id, player);
      ...
```

## riiablo:d8570e136d8a:15 — REMOVE_LOG

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/d8570e136d8ad4c7ed344d98b9a59ddacd777b70
- method: `Excel.loadTxt(T,TxtParser)` in `core/src/main/java/com/riiablo/excel/Excel.java`
- removed statement (pre-state): `log.trace("{}={}", field.getName(), value)`
- levels: TRACE -> None

Pre-state:
```java
      ...
  261                  if (DEBUG_ENTRIES) log.trace("{}={}", field.getName(), value);
  262                } else if (type == String[].class) {
  263                  String[] value = parser.getString(columnIds);
  264                  field.set(entry, value);
  265                  if (DEBUG_ENTRIES) log.trace("{}={}", field.getName(), value);
  266                } else if (type == byte.class) {
  267                  byte value = parser.getByte(columnIds[0]);
  268                  field.setByte(entry, value);
  269                  if (DEBUG_ENTRIES) log.trace("{}={}", field.getName(), value);
  270                } else if (type == byte[].class) {
  271                  byte[] value = parser.getByte(columnIds);
  272                  field.set(entry, value);
  273                  if (DEBUG_ENTRIES) log.trace("{}={}", field.getName(), value);
  274                } else if (type == short.class) {
  275                  short value = parser.getShort(columnIds[0]);
  276                  field.setShort(entry, value);
  277                  if (DEBUG_ENTRIES) log.trace("{}={}", field.getName(), value);
  278                } else if (type == short[].class) {
  279                  short[] value = parser.getShort(columnIds);
  280                  field.set(entry, value);
  281 >>               if (DEBUG_ENTRIES) log.trace("{}={}", field.getName(), value);
  282                } else if (type == int.class) {
  283                  int value = parser.getInt(columnIds[0]);
  284                  field.setInt(entry, value);
  285                  if (DEBUG_ENTRIES) log.trace("{}={}", field.getName(), value);
  286                } else if (type == int[].class) {
  287                  int[] value = parser.getInt(columnIds);
  288                  field.set(entry, value);
  289                  if (DEBUG_ENTRIES) log.trace("{}={}", field.getName(), value);
  290                } else if (type == long.class) {
  291                  long value = parser.getLong(columnIds[0]);
  292                  field.setLong(entry, value);
  293                  if (DEBUG_ENTRIES) log.trace("{}={}", field.getName(), value);
  294                } else if (type == long[].class) {
  295                  long[] value = parser.getLong(columnIds);
  296                  field.set(entry, value);
  297                  if (DEBUG_ENTRIES) log.trace("{}={}", field.getName(), value);
  298                } else if (type == boolean.class) {
  299                  boolean value = parser.getBoolean(columnIds[0]);
  300                  field.setBoolean(entry, value);
  301                  if (DEBUG_ENTRIES) log.trace("{}={}", field.getName(), value);
      ...
```
Post-state:
```java
  130    static <E extends Entry, S extends Serializer<E>, T extends Excel<E, S>>
  131      T loadTxt(T excel, TxtParser parser)
  132          throws IOException, ParseException, IllegalAccessException
  133      {
  134        final Class<E> entryClass = excel.entryClass();
  135        final boolean indexed = ClassUtils.hasAnnotation(entryClass, Indexed.class);
  136    
  137        final String[] TMP = new String[1];
  138        Field primaryKey = null, firstKey = null;
  139        Array<Triple<Field, int[], String[]>> columns = new Array<>(true, parser.numColumns(), Triple.class);
  140        for (Field field : entryClass.getFields()) {
  141          Entry.Column column = field.getAnnotation(Entry.Column.class);
  142          if (column == null) {
  143            log.warn("{} is not tagged with {}", field, Entry.Column.class.getCanonicalName());
  144            continue;
  145          }
  146    
  147          PrimaryKey key = field.getAnnotation(PrimaryKey.class);
  148          if (key != null) {
  149            if (!ArrayUtils.contains(PrimaryKey.SUPPORTED_TYPES, field.getType())) {
  150              throw new ParseException(field, "%s must be one of %s",
      ...
```

## Mindustry:7b8de91b8c57:1 — REMOVE_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/7b8de91b8c5786ee36680da924a4aa814acec09f
- method: `Junction.acceptItem(Item,Tile,Tile)` in `core/src/io/anuke/mindustry/world/blocks/types/distribution/Junction.java`
- removed statement (pre-state): `UCore.log("outputting to " + to + " " + to.block().acceptItem(item, to, dest) + " from " + source)`
- levels: INFO -> None

Pre-state:
```java
   36    @Override
   37    	public boolean acceptItem(Item item, Tile dest, Tile source){
   38    		int dir = source.relativeTo(dest.x, dest.y);
   39    		if(dir == -1) return false;
   40    		Tile to = dest.getNearby()[dir];
   41 >> 		UCore.log("outputting to " + to + " " + to.block().acceptItem(item, to, dest) + " from " + source);
   42    		return to != null && to.block().acceptItem(item, to, dest);
   43    	}
```
Post-state:
```java
   34    @Override
   35    	public boolean acceptItem(Item item, Tile dest, Tile source){
   36    		int dir = source.relativeTo(dest.x, dest.y);
   37    		if(dir == -1) return false;
   38    		Tile to = dest.getNearby()[dir];
   39    		return to != null && to.block().acceptItem(item, to, dest);
   40    	}
```

## Mindustry:01f4a9b23b98:3 — REMOVE_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/01f4a9b23b98ace924231cef29e167d53a56f78f
- method: `NetServer.NetServer()` in `core/src/io/anuke/mindustry/core/NetServer.java`
- removed statement (pre-state): `Log.info("&y{0} has connected.", player.name)`
- levels: INFO -> None

Pre-state:
```java
      ...
  114                trace.playerid = player.id;
  115    
  116                //TODO try DeflaterOutputStream
  117                ByteArrayOutputStream stream = new ByteArrayOutputStream();
  118                NetworkIO.writeWorld(player, stream);
  119                WorldData data = new WorldData();
  120                data.stream = new ByteArrayInputStream(stream.toByteArray());
  121                Net.sendStream(id, data);
  122    
  123                Log.info("Packed {0} uncompressed bytes of WORLD data.", stream.size());
  124    
  125                Platform.instance.updateRPC();
  126            });
  127    
  128            Net.handleServer(ConnectConfirmPacket.class, (id, packet) -> {
  129                Player player = connections.get(id);
  130    
  131                if (player == null) return;
  132    
  133                player.add();
  134 >>             Log.info("&y{0} has connected.", player.name);
  135                netCommon.sendMessage("[accent]" + player.name + " has connected.");
  136            });
  137    
  138            Net.handleServer(Disconnect.class, (id, packet) -> {
  139                Player player = connections.get(packet.id);
  140    
  141                if (player == null) {
  142                    Log.err("Unknown client has disconnected (ID={0})", id);
  143                    return;
  144                }
  145    
  146                Log.info("&y{0} has disconnected.", player.name);
  147                netCommon.sendMessage("[accent]" + player.name + " has disconnected.");
  148                player.remove();
  149    
  150                DisconnectPacket dc = new DisconnectPacket();
  151                dc.playerid = player.id;
  152    
  153                Net.send(dc, SendMode.tcp);
  154    
      ...
```
Post-state:
```java
   38    public NetServer(){
   39    
   40            Net.handleServer(Connect.class, (id, connect) -> {
   41                if(admins.isIPBanned(connect.addressTCP)){
   42                    kick(id, KickReason.banned);
   43                }
   44            });
   45    
   46            Net.handleServer(ClientSnapshotPacket.class, (id, packet) -> {
   47                //...don't do anything here as it's already handled by the packet itself
   48            });
   49    
   50            Net.handleServer(InvokePacket.class, (id, packet) -> {
   51                //TODO implement
   52                //CallServer.readPacket(packet.writeBuffer, packet.type, connections.get(id));
   53            });
   54        }
```

## Mindustry:cd019ab32992:0 — REMOVE_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/cd019ab329928bc4b09115001b93673322adb323
- method: `Conveyor.ConveyorEntity.draw()` in `core/src/mindustry/world/blocks/distribution/Conveyor.java`
- removed statement (pre-state): `Log.info("--DID NOT UPDATE {0}", tile)`
- levels: INFO -> None

Pre-state:
```java
  125    @Override
  126            public void draw(){
  127                if(!everupdated){
  128 >>                 Log.info("--DID NOT UPDATE {0}", tile);
  129                }
  130                byte rotation = tile.rotation();
  131                int frame = clogHeat <= 0.5f ? (int)(((Time.time() * speed * 8f * timeScale())) % 4) : 0;
  132                Draw.rect(regions[Mathf.clamp(blendbits, 0, regions.length - 1)][Mathf.clamp(frame, 0, regions[0].length - 1)], x, y,
  133                tilesize * blendsclx, tilesize * blendscly, rotation * 90);
  134            }
```
Post-state:
```java
  124    @Override
  125            public void draw(){
  126                byte rotation = tile.rotation();
  127                int frame = clogHeat <= 0.5f ? (int)(((Time.time() * speed * 8f * timeScale())) % 4) : 0;
  128                Draw.rect(regions[Mathf.clamp(blendbits, 0, regions.length - 1)][Mathf.clamp(frame, 0, regions[0].length - 1)], x, y,
  129                tilesize * blendsclx, tilesize * blendscly, rotation * 90);
  130            }
```

## OpenKeeper:6fb01ccb729d:0 — REMOVE_LOG

- repo: OpenKeeper  commit: https://github.com/tonihele/OpenKeeper/commit/6fb01ccb729dbac32f33c471f7546b973afa70fa
- method: `PlayerState.setText(int,boolean,int)` in `src/toniarts/openkeeper/game/state/PlayerState.java`
- removed statement (pre-state): `logger.warning(ex.getStackTrace().toString())`
- levels: WARN -> None

Pre-state:
```java
  300    public void setText(int textId, boolean introduction, int pathId) {
  301            Label text = app.getNifty().getNifty().getScreen(CINEMATIC_SCREEN_ID).findNiftyControl("speechText", Label.class);
  302            if (text != null && text.getElement() != null) {
  303                try {
  304                    // FIXME why exeption ???
  305                    text.setText(String.format("${level.%d}", textId));
  306                } catch (Exception ex) {
  307 >>                 logger.warning(ex.getStackTrace().toString());
  308                }
  309            }
  310        }
```
Post-state:
```java
  301    public void setText(int textId, boolean introduction, int pathId) {
  302            this.textId = textId;
  303        }
```

## Mindustry:c2405a882cff:0 — REMOVE_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/c2405a882cff5c65196018c0dae215e71247b68c
- method: `.loadServers()` in `core/src/mindustry/ui/dialogs/JoinDialog.java`
- removed statement (pre-state): `Log.info("Fetching community servers at @", url)`
- levels: INFO -> None

Pre-state:
```java
  624    @SuppressWarnings("unchecked")
  625        private void loadServers(){
  626            servers = Core.settings.getJson("servers", Seq.class, Server.class, Seq::new);
  627    
  628            //load imported legacy data
  629            if(Core.settings.has("server-list")){
  630                servers = LegacyIO.readServers();
  631                Core.settings.remove("server-list");
  632            }
  633    
  634            var url = Version.type.equals("bleeding-edge") || Vars.forceBeServers ? serverJsonBeURL : serverJsonURL;
  635 >>         Log.info("Fetching community servers at @", url);
  636    
  637            //get servers
  638            Http.get(url)
  639            .error(t -> Log.err("Failed to fetch community servers", t))
  640            .submit(result -> {
  641                Jval val = Jval.read(result.getResultAsString());
  642                Seq<ServerGroup> servers = new Seq<>();
  643                val.asArray().each(child -> {
  644                    String name = child.getString("name", "");
  645                    boolean prioritized = child.getBool("prioritized", false);
  646                    String[] addresses;
  647                    if(child.has("addresses") || (child.has("address") && child.get("address").isArray())){
  648                        addresses = (child.has("addresses") ? child.get("addresses") : child.get("address")).asArray().map(Jval::asString).toArray(String.class);
  649                    }else{
  650                        addresses = new String[]{child.getString("address", "<invalid>")};
  651                    }
  652                    servers.add(new ServerGroup(name, addresses, prioritized));
  653                });
  654                //modify default servers on main thread
  655                Core.app.post(() -> {
      ...
```
Post-state:
```java
  624    @SuppressWarnings("unchecked")
  625        private void loadServers(){
  626            servers = Core.settings.getJson("servers", Seq.class, Server.class, Seq::new);
  627    
  628            //load imported legacy data
  629            if(Core.settings.has("server-list")){
  630                servers = LegacyIO.readServers();
  631                Core.settings.remove("server-list");
  632            }
  633    
  634            var urls = Version.type.equals("bleeding-edge") || Vars.forceBeServers ? serverJsonBeURLs : serverJsonURLs;
  635    
  636            fetchServers(urls, 0);
  637        }
```

## SkyHussars:ba4c645491c3:3 — REMOVE_LOG

- repo: SkyHussars  commit: https://github.com/ZoltanTheHun/SkyHussars/commit/ba4c645491c340544f8de5b47f0366c6a4f0fadb
- method: `AdvancedPlanePhysics.calculateAirfoilForces(Quaternion,Vector3f)` in `src/main/java/com/codebetyars/skyhussars/engine/physics/AdvancedPlanePhysics.java`
- removed statement (pre-state): `logger.debug("Airfoilforce points to: " + airfoilForce.toString()/*.normalize().dot(situation.mult(Vector3f.UNIT_Y))*/)`
- levels: DEBUG -> None

Pre-state:
```java
  150    private ActingForces calculateAirfoilForces(Quaternion rotation, Vector3f vFlow) {
  151            Vector3f vLinearAcceleration = Vector3f.ZERO;
  152            Vector3f vTorque = Vector3f.ZERO;
  153            for (Airfoil airfoil : airfoils) {
  154                logger.debug("flow " + vFlow + ", rotation" + rotation + ", angular velocity " + vAngularVelocity);
  155                Vector3f airfoilForce = airfoil.calculateResultantForce(airDensity, vFlow, rotation, vAngularVelocity);
  156 >>             logger.debug("Airfoilforce points to: " + airfoilForce.toString()/*.normalize().dot(situation.mult(Vector3f.UNIT_Y))*/);
  157                logger.debug("rotation" + rotation + ", linear" + vLinearAcceleration + ", airfoil " + airfoilForce);
  158                vLinearAcceleration = vLinearAcceleration.add(airfoilForce);
  159                airfoilForce = rotation.inverse().mult(airfoilForce);
  160                Vector3f distFromCenter = airfoil.getCenterOfGravity();
  161                logger.debug("Airfoilforce points to: " + airfoilForce.toString());
  162                vTorque = vTorque.add(distFromCenter.cross(airfoilForce));
  163            }
  164            return new ActingForces(vLinearAcceleration, vTorque);
  165        }
```
Post-state:
```java
  150    private ActingForces calculateAirfoilForces(Quaternion rotation, Vector3f vFlow) {
  151            Vector3f vLinearAcceleration = Vector3f.ZERO;
  152            Vector3f vTorque = Vector3f.ZERO;
  153            for (Airfoil airfoil : airfoils) {
  154                Vector3f airfoilForce = airfoil.calculateResultantForce(airDensity, vFlow, rotation, vAngularVelocity);
  155                vLinearAcceleration = vLinearAcceleration.add(airfoilForce);
  156                airfoilForce = rotation.inverse().mult(airfoilForce);
  157                Vector3f distFromCenter = airfoil.getCenterOfGravity();
  158                vTorque = vTorque.add(distFromCenter.cross(airfoilForce));
  159            }
  160            return new ActingForces(vLinearAcceleration, vTorque);
  161        }
```

## OpenRTS:82cd86d1d08a:0 — REMOVE_LOG

- repo: OpenRTS  commit: https://github.com/methusalah/OpenRTS/commit/82cd86d1d08a4df024902f6b0167ce29541d6433
- method: `ModelPerformer.drawAsComp(ModelActor)` in `core/src/view/acting/ModelPerformer.java`
- removed statement (pre-state): `LogUtil.logger.info("rotations : roll x : "+comp.roll+"/ pitch y : "+comp.pitch+"/ yaw z : "+actor.getYaw())`
- levels: INFO -> None

Pre-state:
```java
      ...
   80    		if (actor.getComp().direction != null) {
   81    			Point3D pu = actor.getComp().upDirection;
   82    			Point3D pv = actor.getComp().direction;
   83    			if (pu != null) {
   84    				// the comp has a up vector
   85    				// for ground comps or horitonally flying units 
   86    				Vector3f u = Translator.toVector3f(pu).normalize();
   87    				Vector3f v = Translator.toVector3f(pv).normalize();
   88    				r.lookAt(v, u);
   89    //				double angle = Math.acos(pu.getDotProduct(pv) / (pu.getNorm() * pv.getNorm()));
   90    //				r = r.mult(new Quaternion().fromAngles(-(float) angle, 0, 0));
   91    			} else {
   92    				// the comp hasn't any up vector
   93    				// for projectiles
   94    				Vector3f u = new Vector3f(0, -1, 0);
   95    				Vector3f v = Translator.toVector3f(pv).normalize();
   96    				float real = 1 + u.dot(v);
   97    				Vector3f w = u.cross(v);
   98    				r = new Quaternion(w.x, w.y, w.z, real).normalizeLocal();
   99    			}
  100 >> 			LogUtil.logger.info("rotations : roll x : "+comp.roll+"/ pitch y : "+comp.pitch+"/ yaw z : "+actor.getYaw());
  101    		} else {
  102    			r.fromAngles((float)comp.roll, (float)comp.pitch, (float) actor.getYaw());
  103    		}
  104    		s.setLocalRotation(r);
  105    
  106    		if (actor.getComp() instanceof Unit) {
  107    			drawAsUnit(actor);
  108    		} else if (actor.getComp() instanceof Projectile) {
  109    			drawAsProjectile(actor);
  110    		} else if (actor.getComp() instanceof Trinket) {
  111    			drawAsTrinket(actor);
  112    		}
  113    	}
```
Post-state:
```java
   68    protected void drawAsComp(ModelActor actor) {
   69    		Spatial s = actor.getViewElements().spatial;
   70    		FieldComp comp = actor.getComp(); 
   71    		// save the unitid in the userdata
   72    		// TODO, may be set once in the spatial creation
   73    		s.setUserData(ENTITYID_USERDATA, comp.getId());
   74    
   75    		// translation
   76    		s.setLocalTranslation(Translator.toVector3f(actor.getPos()));
   77    
   78    		// rotation
   79    		Quaternion r = new Quaternion();
   80    		if (actor.getComp().direction != null) {
   81    			Point3D pu = actor.getComp().upDirection;
   82    			Point3D pv = actor.getComp().direction;
   83    			if (pu != null) {
   84    				// the comp has a up vector
   85    				// for ground comps or horitonally flying units 
   86    				Vector3f u = Translator.toVector3f(pu).normalize();
   87    				Vector3f v = Translator.toVector3f(pv).normalize();
   88    				r.lookAt(v, u);
      ...
```

## OpenRTS:16472d996b93:7 — REMOVE_LOG

- repo: OpenRTS  commit: https://github.com/methusalah/OpenRTS/commit/16472d996b93f6feffef70c1d8f96f483075d167
- method: `MapRenderer.renderTiles()` in `RTSForGit/src/view/mapDrawing/MapRenderer.java`
- removed statement (pre-state): `LogUtil.logger.info("rendering cliffs")`
- levels: INFO -> None

Pre-state:
```java
   74    public void renderTiles() {
   75                LogUtil.logger.info("rendering ground");
   76    
   77                for(ParcelMesh mesh : parcelManager.meshes){
   78                    Geometry g = new Geometry();
   79                    Mesh jmeMesh = Translator.toJMEMesh(mesh);
   80    //                TangentBinormalGenerator.generate(mesh);
   81                    g.setMesh(jmeMesh);
   82                    g.setMaterial(mm.getTerrain("textures/alphamap.png",
   83                            "textures/grass.tga",
   84                            "textures/road.jpg",
   85                            "textures/road.jpg",
   86                            "textures/road_normal.png"));
   87                    g.setShadowMode(RenderQueue.ShadowMode.Receive);
   88    //                g.addControl(new RigidBodyControl(0));
   89                    parcelsSpatial.put(mesh, g);
   90                    mainNode.attachChild(g);
   91    //                mainPhysicsSpace.add(g);
   92                }
   93    
   94 >>             LogUtil.logger.info("rendering cliffs");
   95                for(Tile t : map.getTilesWithCliff()) {
   96                    if(t.cliff.naturalFace == null)
   97                        continue;
   98                    if(t.cliff.manmadeFace == null){
   99                        Geometry g = new Geometry();
  100                        g.setMesh(Translator.toJMEMesh(t.cliff.naturalFace.mesh));
  101                        g.setMaterial(mm.getLightingTexture("textures/road.jpg"));
  102                        g.setShadowMode(RenderQueue.ShadowMode.CastAndReceive);
  103    
  104                        g.rotate(0, 0, (float)(t.cliff.angle));
  105                        g.setLocalTranslation(t.x+0.5f, t.y+0.5f, (float)(t.level*Tile.STAGE_HEIGHT));
  106    
  107                        tilesSpatial.put(t, g);
  108                        mainNode.attachChild(g);
  109    
  110                        for(Trinket a : t.cliff.naturalFace.getAssets()){
  111                            Spatial s = getModel(a.path);
  112                            s.scale(0.002f*(float)a.scale);
  113                            s.rotate((float)a.rotX, (float)a.rotY, (float)a.rotZ);
  114                            if(a.path.equals("models/env/exterior01/rockA.mesh.xml"))
      ...
```
Post-state:
```java
   83    public void renderTiles() {
   84                LogUtil.logger.info("rendering ground");
   85                for(ParcelMesh mesh : parcelManager.meshes){
   86                    Geometry g = new Geometry();
   87                    Mesh jmeMesh = Translator.toJMEMesh(mesh);
   88    //                TangentBinormalGenerator.generate(mesh);
   89                    g.setMesh(jmeMesh);
   90                    g.setMaterial(mm.getTerrain("textures/alphamap.png",
   91                            "textures/grass.png",
   92                            "textures/road.jpg",
   93                            "textures/road.jpg",
   94                            "textures/road_normal.png"));
   95    //                g.addControl(new RigidBodyControl(0));
   96                    parcelsSpatial.put(mesh, g);
   97                    castAndReceiveNode.attachChild(g);
   98    //                mainPhysicsSpace.add(g);
   99                }
  100        }
```

## Mindustry:47e723c55764:1 — REMOVE_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/47e723c55764e8b0505dcb03bc2ee18c48296278
- method: `ServerControl.play(boolean,Runnable)` in `server/src/io/anuke/mindustry/server/ServerControl.java`
- removed statement (pre-state): `Log.info("Group contents post:\n{0}\n{1}\n\n", players, playerGroup.all())`
- levels: INFO -> None

Pre-state:
```java
  799    private void play(boolean wait, Runnable run){
  800            inExtraRound = true;
  801            Runnable r = () -> {
  802                Array<Player> players = new Array<>();
  803                for(Player p : playerGroup.all()){
  804                    players.add(p);
  805                    p.setDead(true);
  806                }
  807    
  808                Log.info("Group contents:\n{0}\n{1}\n\n", players, playerGroup.all());
  809                
  810                logic.reset();
  811    
  812                Call.onWorldDataBegin();
  813                run.run();
  814                logic.play();
  815                state.rules = world.getMap().applyRules(lastMode);
  816    
  817 >>             Log.info("Group contents post:\n{0}\n{1}\n\n", players, playerGroup.all());
  818    
  819                for(Player p : players){
  820                    p.reset();
  821                    if(state.rules.pvp){
  822                        p.setTeam(netServer.assignTeam(p, new ArrayIterable<>(players)));
  823                    }
  824                    netServer.sendWorldData(p);
  825                }
  826                inExtraRound = false;
  827            };
  828    
  829            if(wait){
  830                lastTask = new Task(){
  831                    @Override
  832                    public void run(){
  833                        try{
  834                            r.run();
  835                        }catch(MapException e){
  836                            Log.err(e.map.name() + ": " + e.getMessage());
  837                            net.closeServer();
      ...
```
Post-state:
```java
  799    private void play(boolean wait, Runnable run){
  800            inExtraRound = true;
  801            Runnable r = () -> {
  802                Array<Player> players = new Array<>();
  803                for(Player p : playerGroup.all()){
  804                    players.add(p);
  805                    p.setDead(true);
  806                }
  807                
  808                logic.reset();
  809    
  810                Call.onWorldDataBegin();
  811                run.run();
  812                logic.play();
  813                state.rules = world.getMap().applyRules(lastMode);
  814    
  815                for(Player p : players){
  816                    p.reset();
  817                    if(state.rules.pvp){
  818                        p.setTeam(netServer.assignTeam(p, new ArrayIterable<>(players)));
  819                    }
      ...
```

## Mindustry:be2fa1dfad22:1 — REMOVE_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/be2fa1dfad229eba595f10046f049eac4a2e3ee0
- method: `Player.removed()` in `core/src/io/anuke/mindustry/entities/Player.java`
- removed statement (pre-state): `Log.info("\n\nPLAYER REMOVED\n\n")`
- levels: INFO -> None

Pre-state:
```java
  195    @Override
  196    	public void removed() {
  197 >> 		Log.info("\n\nPLAYER REMOVED\n\n");
  198            dropCarry();
  199    	}
```
Post-state:
```java
  202    @Override
  203    	public void removed() {
  204            dropCarry();
  205    	}
```

## riiablo:c12747500748:16 — REMOVE_LOG

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/c127475007483b9c27634787fbf894500c509938
- method: `StatList.sub(int,short,StatList,int)` in `core/src/com/riiablo/attributes/StatList.java`
- removed statement (pre-state): `log.info(indexDebugString(index))`
- levels: INFO -> None

Pre-state:
```java
  336    @Deprecated
  337      public boolean sub(int list, short stat, StatList src, int srcList) {
  338        if (true) throw new UnsupportedOperationException();
  339        assertMutable();
  340        log.traceEntry("sub(list: {}, stat: {}, src: {}, srcList: {})", list, stat, src, srcList);
  341        assert !Stat.hasParams(stat) : "stat(" + stat + ") requires params";
  342        assert encoding(stat) <= 2 : "#sub() unsupported for encoding(" + encoding(stat) + ")";
  343        final int index = indexOf(list, stat, 0);
  344        final int otherIndex = src.indexOf(srcList, stat, 0);
  345        if (log.debugEnabled()) log.debug(
  346            "sub(stat: {} ({}), this: {}, src: {})",
  347            stat, entry(stat), index >= 0 ? asString(index) : "null", src.asString(otherIndex));
  348        assert index >= 0 : "property list does not contain stat(" + stat + ")";
  349        if (index < 0) return false; // indefined behavior
  350        values[index] -= src.values[otherIndex];
  351 >>     if (log.infoEnabled()) log.info(indexDebugString(index));
  352        // TODO: if values[index] <= 0, remove it? is <= 0 appropriate
  353        return true;
  354        // min
  355      }
```
Post-state:
```java
  292    @Deprecated
  293      public boolean sub(final int list, final short stat, final StatList src, final int srcList) {
  294        throw new UnsupportedOperationException();
  295      }
```

## riiablo:86c4e6d8efd3:14 — REMOVE_LOG

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/86c4e6d8efd3be6103a50570ba5cd5a543a5ae92
- method: `GameScreen.show()` in `core/src/gdx/diablo/screen/GameScreen.java`
- removed statement (pre-state): `Gdx.app.debug(TAG, player.toString())`
- levels: DEBUG -> None

Pre-state:
```java
      ...
  382      public void show() {
  383        Diablo.music.stop();
  384        Diablo.assets.get(windowopenDescriptor).play();
  385    
  386        map = Diablo.assets.get(mapDescriptor);
  387        camera = new OrthographicCamera(Diablo.VIRTUAL_WIDTH, Diablo.VIRTUAL_HEIGHT);
  388        mapRenderer = new MapRenderer(Diablo.batch, camera);
  389        mapRenderer.setMap(map);
  390        mapRenderer.resize();
  391    
  392        GridPoint2 origin = map.find(Map.ID.TOWN_ENTRY_1);
  393        mapRenderer.setPosition(origin);
  394        if (Gdx.app.getType() == Application.ApplicationType.Android) {
  395          camera.zoom = 0.80f;
  396          camera.update();
  397        }
  398    
  399        //character.x = origin.x;
  400        //character.y = origin.y;
  401        player.origin().set(origin);
  402 >>     Gdx.app.debug(TAG, player.toString());
  403    
  404        Keys.Esc.addStateListener(mappedKeyStateListener);
  405        Keys.Inventory.addStateListener(mappedKeyStateListener);
  406        Keys.Character.addStateListener(mappedKeyStateListener);
  407        Keys.Stash.addStateListener(mappedKeyStateListener);
  408        Keys.SwapWeapons.addStateListener(mappedKeyStateListener);
  409        Keys.Enter.addStateListener(mappedKeyStateListener);
  410        Diablo.input.addProcessor(stage);
  411        Diablo.input.addProcessor(inputProcessorTest);
  412    
  413        if (socket != null && socket.isConnected()) {
  414          Gdx.app.log(TAG, "connecting to " + socket.getRemoteAddress() + "...");
  415          in = IOUtils.buffer(new InputStreamReader(socket.getInputStream()));
  416          out = new PrintWriter(socket.getOutputStream(), true);
  417        }
  418    
  419        updateTask = Timer.schedule(new Timer.Task() {
  420          @Override
  421          public void run() {
  422            if (UIUtils.shift()) return;
      ...
```
Post-state:
```java
  392    @Override
  393      public void show() {
  394        Diablo.music.stop();
  395        Diablo.assets.get(windowopenDescriptor).play();
  396    
  397        map = Diablo.assets.get(mapDescriptor);
  398        camera = new OrthographicCamera(Diablo.VIRTUAL_WIDTH, Diablo.VIRTUAL_HEIGHT);
  399        mapRenderer = new MapRenderer(Diablo.batch, camera);
  400        mapRenderer.setMap(map);
  401        mapRenderer.resize();
  402    
  403        GridPoint2 origin = map.find(Map.ID.TOWN_ENTRY_1);
  404        mapRenderer.setPosition(origin);
  405        if (Gdx.app.getType() == Application.ApplicationType.Android) {
  406          camera.zoom = 0.80f;
  407          camera.update();
  408        }
  409    
  410        //character.x = origin.x;
  411        //character.y = origin.y;
  412        player.position().set(origin.x, origin.y, 0);
      ...
```

## riiablo:c10083d1ea46:20 — REMOVE_LOG

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/c10083d1ea4688613d568b0a8117fccdbebd0925
- method: `Dcc.DccDirection.DccDirection(BitInput,int)` in `core/src/main/java/com/riiablo/file/Dcc.java`
- removed statement (pre-state): `log.trace("rawPixelCodesBitStreamSize: {} bits", rawPixelCodesBitStreamSize)`
- levels: TRACE -> None

Pre-state:
```java
      ...
  197    
  198          box.width++; // why?
  199          box.height++; // why?
  200    
  201          if (optionalBytes > 0) {
  202            for (int frame = 0; frame < numFrames; frame++) {
  203              DccFrame f = frames[frame];
  204              if (f.optionalBytes > 0) {
  205                f.optionalData = bits.align().readSlice(f.optionalBytes);
  206              }
  207            }
  208          }
  209    
  210          equalCellBitStreamSize = (compressionFlags & CompressEqualCells) == CompressEqualCells ? bits.read31u(20) : 0;
  211          log.trace("equalCellBitStreamSize: {} bits", equalCellBitStreamSize);
  212          pixelMaskBitStreamSize = bits.read31u(20);
  213          log.trace("pixelMaskBitStreamSize: {} bits", pixelMaskBitStreamSize);
  214          encodingTypeBitStreamSize = (compressionFlags & HasRawPixelEncoding) == HasRawPixelEncoding ? bits.read31u(20) : 0;
  215          log.trace("encodingTypeBitStreamSize: {} bits", encodingTypeBitStreamSize);
  216          rawPixelCodesBitStreamSize = (compressionFlags & HasRawPixelEncoding) == HasRawPixelEncoding ? bits.read31u(20) : 0;
  217 >>       log.trace("rawPixelCodesBitStreamSize: {} bits", rawPixelCodesBitStreamSize);
  218    
  219          pixelValues = new byte[Palette.COLORS];
  220          readPixelValues(bits, pixelValues);
  221    
  222          assert (compressionFlags & CompressEqualCells) != CompressEqualCells || equalCellBitStreamSize > 0;
  223          equalCellBitStream = bits.readSlice(equalCellBitStreamSize);
  224          pixelMaskBitStream = bits.readSlice(pixelMaskBitStreamSize);
  225          assert (compressionFlags & HasRawPixelEncoding) != HasRawPixelEncoding
  226              || (encodingTypeBitStreamSize > 0 && rawPixelCodesBitStreamSize > 0);
  227          encodingTypeBitStream = bits.readSlice(encodingTypeBitStreamSize);
  228          rawPixelCodesBitStream = bits.readSlice(rawPixelCodesBitStreamSize);
  229          pixelCodeAndDisplacementBitStream = bits.readSlice(bits.bitsRemaining());
  230        }
```
Post-state:
```java
  135    DccDirection(BitInput bits, int numFrames) {
  136          uncompressedSize = bits.readSafe32u();
  137          compressionFlags = (byte) bits.readRaw(2);
  138          variable0Bits = bits.read7u(4);
  139          widthBits = bits.read7u(4);
  140          heightBits = bits.read7u(4);
  141          xOffsetBits = bits.read7u(4);
  142          yOffsetBits = bits.read7u(4);
  143          extraBytesBits = bits.read7u(4);
  144          compressedBytesBits = bits.read7u(4);
  145    
  146          box = new BBox().prepare();
  147          DccFrame[] frames = this.frames = new DccFrame[numFrames];
  148    
  149          long extraBytes = 0;
  150          for (int frame = 0; frame < numFrames; frame++) {
  151            try {
  152              MDC.put("frame", frame);
  153              DccFrame f = frames[frame] = new DccFrame(
  154                  bits,
  155                  variable0Bits,
      ...
```

## Mindustry:8a84ebb58d44:0 — REMOVE_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/8a84ebb58d44ecc8af1ba90332e6d1f4bb77132a
- method: `NetConnection.kick(KickReason)` in `core/src/mindustry/net/NetConnection.java`
- removed statement (pre-state): `Log.info("Kicking connection @ / @; Reason: @", address, uuid, reason.name())`
- levels: INFO -> None

Pre-state:
```java
   39    public void kick(KickReason reason){
   40            if(kicked) return;
   41    
   42 >>         Log.info("Kicking connection @ / @; Reason: @", address, uuid, reason.name());
   43    
   44            if((reason == KickReason.kick || reason == KickReason.banned || reason == KickReason.vote)){
   45                PlayerInfo info = netServer.admins.getInfo(uuid);
   46                info.timesKicked++;
   47                info.lastKicked = Math.max(Time.millis() + 30 * 1000, info.lastKicked);
   48            }
   49    
   50            Call.kick(this, reason);
   51    
   52            close();
   53    
   54            netServer.admins.save();
   55            kicked = true;
   56        }
```
Post-state:
```java
   38    public void kick(KickReason reason){
   39            kick(reason, (reason == KickReason.kick || reason == KickReason.banned || reason == KickReason.vote) ? 30 * 1000 : 0);
   40        }
```

## subspace-infinity:8283ec8c3c64:28 — REMOVE_LOG

- repo: subspace-infinity  commit: https://github.com/assofohdz/subspace-infinity/commit/8283ec8c3c64a578c3a479684ab93a2f9a802fb5
- method: `ModelViewState.updateCenter(Vector3f)` in `infinity/src/main/java/infinity/client/view/ModelViewState.java`
- removed statement (pre-state): `log.info("cell:" + cell + "   lastCell:" + centerCell)`
- levels: INFO -> None

Pre-state:
```java
  410    protected void updateCenter(final Vector3f center) {
  411            // log.info("updateCenter(" + center + ")");
  412    
  413            final Vector3f cell = worldView.getViewCell();
  414    
  415            // If the cell position has moved then we need to recalculate
  416            // relative positions of static objects
  417            if ((int) cell.x != centerCell.x || (int) cell.y != centerCell.y || (int) cell.z != centerCell.z) {
  418 >>             log.info("cell:" + cell + "   lastCell:" + centerCell);
  419    
  420                centerCell.x = (int) cell.x;
  421                centerCell.y = (int) cell.y;
  422                centerCell.z = (int) cell.z;
  423                worldView.cellToWorld(centerCell, centerCellWorld);
  424                centerCellWorld.y = 0;
  425                resetRelativeCoordinates();
  426    
  427                if (modelCenter.x != centerCell.x || modelCenter.z != centerCell.z) {
  428                    modelCenter.x = centerCell.x;
  429                    modelCenter.z = centerCell.z;
  430                    // Also need to reset the filter for the static objects
  431                    resetModelFilter();
  432                }
  433    
  434                // Calculate the large model center cell
  435                final Vec3i largeCenter = InfinityConstants.LARGE_OBJECT_GRID.worldToCell(new Vec3d(centerCellWorld));
  436                if (largeModelCenter.x != largeCenter.x || largeModelCenter.z != largeCenter.z) {
  437                    largeModelCenter.x = largeCenter.x;
  438                    largeModelCenter.z = largeCenter.z;
      ...
```
Post-state:
```java
  379    protected void updateCenter( Vector3f center ) {
  380            //log.info("updateCenter(" + center + ")");
  381    
  382            Vector3f cell = worldView.getViewCell();
  383    
  384            //log.info("cell:" + cell + "   lastCell:" + centerCell);
  385    
  386            // If the cell position has moved then we need to recalculate
  387            // relative positions of static objects
  388            if( (int)cell.x != centerCell.x || (int)cell.y != centerCell.y || (int)cell.z != centerCell.z ) {
  389                centerCell.x = (int)cell.x;
  390                centerCell.y = (int)cell.y;
  391                centerCell.z = (int)cell.z;
  392                worldView.cellToWorld(centerCell, centerCellWorld);
  393                //centerCellWorld.y = 0;
  394                resetRelativeCoordinates();
  395    
  396                if( modelCenter.x != centerCell.x || modelCenter.z != centerCell.z ) {
  397                    modelCenter.x = centerCell.x;
  398                    modelCenter.z = centerCell.z;
  399                    // Also need to reset the filter for the static objects
      ...
```

## OpenKeeper:1efef9d76cb2:0 — REMOVE_LOG

- repo: OpenKeeper  commit: https://github.com/tonihele/OpenKeeper/commit/1efef9d76cb2ec290e24d0997d99dbe9a4042014
- method: `KwdFile.readVariables(KwdHeader,RandomAccessFile)` in `src/toniarts/openkeeper/tools/convert/map/KwdFile.java`
- removed statement (pre-state): `logger.log(Level.INFO, "Id = {0}", id)`
- levels: INFO -> None

Pre-state:
```java
 2470    private void readVariables(KwdHeader header, RandomAccessFile file) throws IOException {
 2471    
 2472            // Read the requested VARIABLES file
 2473            // Should be the GlobalVariables first, then the level's own
 2474            // TODO: Overriding
 2475            logger.info("Reading variables!");
 2476            if (variables == null) {
 2477                variables = new ArrayList<>(header.getItemCount());
 2478            }
 2479            for (int i = 0; i < header.getItemCount(); i++) {
 2480                Variable variable = new Variable();
 2481                int id = ConversionUtils.readInteger(file);
 2482 >>             logger.log(Level.INFO, "Id = {0}", id);
 2483                variable.setX00(id);
 2484                variable.setValue(ConversionUtils.readInteger(file));
 2485                variable.setX08(ConversionUtils.readInteger(file));
 2486                variable.setX0c(ConversionUtils.readInteger(file));
 2487    
 2488                // Add to the list
 2489                variables.add(variable);
 2490            }
 2491        }
```
Post-state:
```java
 2470    private void readVariables(KwdHeader header, RandomAccessFile file) throws IOException {
 2471    
 2472            // Read the requested VARIABLES file
 2473            // Should be the GlobalVariables first, then the level's own
 2474            // TODO: Overriding
 2475            logger.info("Reading variables!");
 2476            if (variables == null) {
 2477                variables = new ArrayList<>(header.getItemCount());
 2478            }
 2479    
 2480            for (int i = 0; i < header.getItemCount(); i++) {
 2481                int id = ConversionUtils.readInteger(file);
 2482                Variable variable;
 2483    
 2484                switch (id) {
 2485                    case Variable.CREATURE_POOL:
 2486                        variable = new Variable.CreaturePool();
 2487                        ((Variable.CreaturePool) variable).setCreatureId(ConversionUtils.readInteger(file));
 2488                        ((Variable.CreaturePool) variable).setValue(ConversionUtils.readInteger(file));
 2489                        ((Variable.CreaturePool) variable).setPlayerId(ConversionUtils.readInteger(file));
 2490                        break;
      ...
```

## riiablo:5a5819329a8a:2 — REMOVE_LOG

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/5a5819329a8a57f4a202f3224cdc36b8ff0fec63
- method: `Player.loadItems(Array<Item>)` in `core/src/com/riiablo/entity/Player.java`
- removed statement (pre-state): `Gdx.app.debug(TAG, item.gridX + "," + item.gridY + ": " + item)`
- levels: DEBUG -> None

Pre-state:
```java
      ...
  169          switch (item.location) {
  170            case EQUIPPED:
  171              equipped.put(item.bodyLoc, item);
  172              if (item.quality == Quality.SET) {
  173                Sets.Entry set = Riiablo.files.SetItems.get(item.qualityId).getSet();
  174                int id = Riiablo.files.Sets.index(set.index);
  175                SETS_EQUIP.getAndIncrement(id, 0, 1);
  176              }
  177              if (DEBUG_EQUIP) Gdx.app.debug(TAG, item.bodyLoc + ": " + item);
  178              break;
  179            case STORED:
  180              store.get(item.storeLoc).add(item);
  181              break;
  182            case BELT:
  183              item.gridY = (byte) -(item.gridX >>> 2);
  184              item.gridX &= 0x3;
  185              System.out.println(item.getName() + ": " + item.gridX + ", " + item.gridY);
  186              belt.add(item);
  187              break;
  188            default:
  189 >>           if (DEBUG_INV) Gdx.app.debug(TAG, item.gridX + "," + item.gridY + ": " + item);
  190          }
  191          if (item.quality == Quality.SET) {
  192            SETS_OWNS.getAndIncrement(item.qualityId, 0, 1);
  193          }
  194          item.load();
  195        }
  196      }
```
Post-state:
```java
  104    private void loadItems(Array<Item> items) {
  105        for (Item item : items) {
  106          //item.setOwner(this);
  107          item.load();
  108        }
  109      }
```

## riiablo:ac35310acea2:2 — REMOVE_LOG

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/ac35310acea2eda6def3ccd095ae98a215a61e70
- method: `LobbyScreen.show()` in `core/src/com/riiablo/screen/LobbyScreen.java`
- removed statement (pre-state): `Gdx.app.log(TAG, "create-session " + error.toString())`
- levels: INFO -> None

Pre-state:
```java
      ...
  287                      desc     = tfDesc.getText();
  288                    }})
  289                    .build();
  290                Gdx.net.sendHttpRequest(request, new Net.HttpResponseListener() {
  291                  @Override
  292                  public void handleHttpResponse(Net.HttpResponse httpResponse) {
  293                    String response = httpResponse.getResultAsString();
  294                    try {
  295                      final Session session = new Json().fromJson(Session.class, response);
  296                      Gdx.app.log(TAG, "create-session " + response);
  297                      Gdx.app.postRunnable(new Runnable() {
  298                        @Override
  299                        public void run() {
  300                          Socket socket = Gdx.net.newClientSocket(Net.Protocol.TCP, session.host, session.port, null);
  301                          Gdx.app.log(TAG, "create-session connect " + session.host + ":" + session.port + " " + socket.isConnected());
  302                          Riiablo.client.pushScreen(new GameLoadingScreen(new GameScreen(player, socket)));
  303                        }
  304                      });
  305                    } catch (SerializationException e) {
  306                      SessionError error = new Json().fromJson(SessionError.class, response);
  307 >>                   Gdx.app.log(TAG, "create-session " + error.toString());
  308                    }
  309                  }
  310    
  311                  @Override
  312                  public void failed(Throwable t) {
  313                    Gdx.app.log(TAG, "create-session " + t.getMessage());
  314                  }
  315    
  316                  @Override
  317                  public void cancelled() {
  318                    Gdx.app.log(TAG, "create-session " + "cancelled");
  319                  }
  320                });
  321              }
  322            });
  323            tfGameName.addListener(new ChangeListener() {
  324              @Override
  325              public void changed(ChangeEvent event, Actor actor) {
  326                btnCreateGame.setDisabled(tfGameName.getText().isEmpty());
  327              }
      ...
```
Post-state:
```java
  123    @Override
  124      public void show() {
  125        Riiablo.viewport = Riiablo.extendViewport;
  126        Riiablo.assets.finishLoadingAsset(waitingroombkgdDescriptor);
  127        waitingroombkgd = Riiablo.assets.get(waitingroombkgdDescriptor).getTexture();
  128    
  129        Riiablo.assets.finishLoadingAsset(blankbckgDescriptor);
  130        blankbckg = Riiablo.assets.get(blankbckgDescriptor).getTexture();
  131    
  132        Riiablo.assets.finishLoadingAsset(creategamebckgDescriptor);
  133        creategamebckg = Riiablo.assets.get(creategamebckgDescriptor).getTexture();
  134    
  135        Riiablo.assets.finishLoadingAsset(joingamebckgDescriptor);
  136        joingamebckg = Riiablo.assets.get(joingamebckgDescriptor).getTexture();
  137    
  138        stage.setDebugAll(true);
  139    
  140        ClickListener clickListener = new ClickListener() {
  141          @Override
  142          public void clicked(InputEvent event, float x, float y) {
  143            Actor actor = event.getListenerActor();
      ...
```

## Mindustry:0c75f920deaf:0 — REMOVE_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/0c75f920deafabfa208ff4072e9c2990964382f0
- method: `MapEditor.draw(int,int,boolean,Block,double)` in `core/src/io/anuke/mindustry/editor/MapEditor.java`
- removed statement (pre-state): `Log.info("Remove linkd: " + tiles[x][y])`
- levels: INFO -> None

Pre-state:
```java
      ...
  193                    }
  194                }
  195    
  196                Tile tile = tiles[x][y];
  197                tile.setBlock(drawBlock);
  198                tile.setTeam(drawTeam);
  199            }else{
  200                for(int rx = -brushSize; rx <= brushSize; rx++){
  201                    for(int ry = -brushSize; ry <= brushSize; ry++){
  202                        if(Mathf.dst(rx, ry) <= brushSize - 0.5f && (chance >= 0.999 || Mathf.chance(chance))){
  203                            int wx = x + rx, wy = y + ry;
  204    
  205                            if(wx < 0 || wy < 0 || wx >= width() || wy >= height() || (paint && !isfloor && tiles[wx][wy].block() == Blocks.air)){
  206                                continue;
  207                            }
  208    
  209                            Tile tile = tiles[wx][wy];
  210    
  211                            if(!isfloor){
  212                                byte link = tile.getLinkByte();
  213 >>                             Log.info("Remove linkd: " + tiles[x][y]);
  214    
  215                                if(tile.block().isMultiblock()){
  216                                    removeLinked(wx, wy);
  217                                }else if(link != 0 && tiles[x][y].block() == Blocks.part){
  218                                    removeLinked(wx - (Pack.leftByte(link) - 8), wy - (Pack.rightByte(link) - 8));
  219                                }
  220                            }
  221    
  222                            if(isfloor){
  223                                tile.setFloor((Floor)drawBlock);
  224                            }else{
  225                                tile.setBlock(drawBlock);
  226                                if(drawBlock.synthetic()){
  227                                    tile.setTeam(drawTeam);
  228                                }
  229                            }
  230                        }
  231                    }
  232                }
  233            }
      ...
```
Post-state:
```java
  157    public void draw(int x, int y, boolean paint, Block drawBlock, double chance){
  158            boolean isfloor = drawBlock instanceof Floor && drawBlock != Blocks.air;
  159    
  160            if(drawBlock.isMultiblock()){
  161                
  162                x = Mathf.clamp(x, (drawBlock.size-1)/2, width() - drawBlock.size/2 - 1);
  163                y = Mathf.clamp(y, (drawBlock.size-1)/2, height() - drawBlock.size/2 - 1);
  164    
  165                int offsetx = -(drawBlock.size - 1) / 2;
  166                int offsety = -(drawBlock.size - 1) / 2;
  167    
  168                for(int i = 0; i < 2; i++){
  169                    for(int dx = 0; dx < drawBlock.size; dx++){
  170                        for(int dy = 0; dy < drawBlock.size; dy++){
  171                            int worldx = dx + offsetx + x;
  172                            int worldy = dy + offsety + y;
  173    
  174                            if(Structs.inBounds(worldx, worldy, width(), height())){
  175                                Tile tile = tiles[worldx][worldy];
  176    
  177                                if(i == 1){
      ...
```

## Mindustry:18b137a1a61d:0 — REMOVE_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/18b137a1a61dcf5e5cb4206f3189f0edc1789f93
- method: `Recipe.init()` in `core/src/io/anuke/mindustry/type/Recipe.java`
- removed statement (pre-state): `Log.err("WARNING: Recipe block '{0}' does not have a description defined.", result.name)`
- levels: ERROR -> None

Pre-state:
```java
   55    @Override
   56        public void init() {
   57            if(!Bundles.has("block." + result.name + ".name")) {
   58                Log.err("WARNING: Recipe block '{0}' does not have a formal name defined.", result.name);
   59            }else if(result.fullDescription == null){
   60 >>             Log.err("WARNING: Recipe block '{0}' does not have a description defined.", result.name);
   61            }
   62        }
```
Post-state:
```java
   59    @Override
   60        public void init() {
   61            if(!Bundles.has("block." + result.name + ".name")) {
   62                Log.err("WARNING: Recipe block '{0}' does not have a formal name defined.", result.name);
   63            }/*else if(result.fullDescription == null){
   64                Log.err("WARNING: Recipe block '{0}' does not have a description defined.", result.name);
   65            }*/
   66        }
```

## subspace-infinity:4ae20d511e4b:3 — REMOVE_LOG

- repo: subspace-infinity  commit: https://github.com/assofohdz/subspace-infinity/commit/4ae20d511e4b7df1f5fe419b680fd6ea66bbe0aa
- method: `SISpatialFactory.updateWangBlobTile(Spatial,TileType)` in `sim-eth-es/src/main/java/example/view/SISpatialFactory.java`
- removed statement (pre-state): `log.info("Coords: "+s.getLocalTranslation() +" rotated: "+geom.getLocalRotation())`
- levels: INFO -> None

Pre-state:
```java
      ...
  582            if (s instanceof Geometry) {
  583                geom = (Geometry) s; 
  584            } else {
  585                geom = (Geometry) ((Node) s).getChild("MapTile"); //From ModelViewState
  586            }
  587            Material mat = geom.getMaterial();
  588            //Offset tile
  589            mat.setInt("numTilesOffsetX", clientMapState.getWangBlobTileNumber(tileType.getTileIndex()));
  590            
  591            //Rotate tile
  592            Quaternion rot = new Quaternion();
  593            float rotations = clientMapState.getWangBlobRotations(tileType.getTileIndex());
  594            float ninety_degrees_to_radians = FastMath.PI/2;
  595            
  596            rot.fromAngleAxis(- ninety_degrees_to_radians * rotations, Vector3f.UNIT_Z);
  597            //Reset rotation
  598            geom.setLocalRotation(new Quaternion());
  599            //Set correct rotation
  600            geom.rotate(rot);
  601            
  602 >>         log.info("Coords: "+s.getLocalTranslation() +" rotated: "+geom.getLocalRotation());
  603            
  604        }
```
Post-state:
```java
  584    public void updateWangBlobTile(Spatial s, TileType tileType) {
  585            Geometry geom;
  586            if (s instanceof Geometry) {
  587                geom = (Geometry) s;
  588            } else {
  589                geom = (Geometry) ((Node) s).getChild("MapTile"); //From ModelViewState
  590            }
  591            Material mat = geom.getMaterial();
  592            //Offset tile
  593            mat.setInt("numTilesOffsetX", clientMapState.getWangBlobTileNumber(tileType.getTileIndex()));
  594    
  595            //Rotate tile
  596            Quaternion rot = new Quaternion();
  597            float rotations = clientMapState.getWangBlobRotations(tileType.getTileIndex());
  598            float ninety_degrees_to_radians = FastMath.PI / 2;
  599    
  600            rot.fromAngleAxis(-ninety_degrees_to_radians * rotations, Vector3f.UNIT_Z);
  601            //Reset rotation
  602            geom.setLocalRotation(new Quaternion());
  603            //Set correct rotation
  604            geom.rotate(rot);
      ...
```

## Mindustry:5012313dc43b:0 — REMOVE_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/5012313dc43b1db4e78c56f7dd5fc668494c02f2
- method: `Pathfinder.test(Tile,Tile)` in `core/src/io/anuke/mindustry/ai/Pathfinder.java`
- removed statement (pre-state): `Log.info("JSFSAF elapsed: {0}", Timers.elapsedNs())`
- levels: INFO -> None

Pre-state:
```java
   23    public void test(Tile start, Tile end){
   24            this.start = start;
   25            this.end = end;
   26    
   27            DefaultGraphPath<Tile> p = new DefaultGraphPath<>();
   28    
   29            OptimizedPathFinder.unop = false;
   30            Timers.markNs();
   31            find.searchNodePath(start, end, p);
   32    
   33 >>         Log.info("JSFSAF elapsed: {0}", Timers.elapsedNs());
   34    
   35            for(Tile tile : p){
   36                Effects.effect(Fx.breakBlock, tile.worldx(), tile.worldy());
   37            }
   38    
   39            SmoothGraphPath p2 = new SmoothGraphPath();
   40    
   41            OptimizedPathFinder.unop = true;
   42            Timers.markNs();
   43            find2.searchNodePath(start, end, p2);
   44            new PathSmoother<Tile, Vector2>(new Raycaster()).smoothPath(p2);
   45    
   46            Log.info("UNOP elapsed: {0}", Timers.elapsedNs());
   47    
   48            for(Tile tile : p2){
   49                Effects.effect(Fx.place, tile.worldx(), tile.worldy());
   50            }
   51    
   52        }
```
Post-state:
```java
   35    public void test(Tile start, Tile end){
   36            SmoothGraphPath p2 = new SmoothGraphPath();
   37    
   38            Timers.markNs();
   39            find.searchNodePath(start, end, p2);
   40            new PathSmoother<Tile, Vector2>(new Raycaster()).smoothPath(p2);
   41    
   42            Log.info("UNOP elapsed: {0}", Timers.elapsedNs());
   43    
   44            for(Tile tile : p2){
   45                Effects.effect(Fx.place, tile.worldx(), tile.worldy());
   46            }
   47    
   48        }
```

## Mindustry:304f5b62b317:0 — REMOVE_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/304f5b62b317b3dcdb15a7b9f1fbc095dcfe272f
- method: `Generators.generate()` in `tools/src/mindustry/tools/Generators.java`
- removed statement (pre-state): `Log.info("saving VOID icon @ / @", icon, "../ui/block-" + block.name + "-" + icon.name())`
- levels: INFO -> None

Pre-state:
```java
      ...
  290                            }
  291    
  292                            //draw shard (default team top) on top of first sprite
  293                            if(region == block.teamRegions[Team.sharded.id] && shardTeamTop != null){
  294                                image.draw(shardTeamTop);
  295                            }
  296                        }
  297    
  298                        if(!(regions.length == 1 && regions[0] == Core.atlas.find(block.name) && shardTeamTop == null)){
  299                            image.save("block-" + block.name + "-full");
  300                        }
  301    
  302                        image.save("../editor/" + block.name + "-icon-editor");
  303    
  304                        for(Cicon icon : Cicon.scaled){
  305                            Image scaled = new Image(icon.size, icon.size);
  306                            scaled.drawScaled(image);
  307                            scaled.save("../ui/block-" + block.name + "-" + icon.name());
  308    
  309                            if(block == Blocks.itemVoid){
  310 >>                             Log.info("saving VOID icon @ / @", icon, "../ui/block-" + block.name + "-" + icon.name());
  311                            }
  312    
  313                            if(icon == logicIcon && block.synthetic() && block.buildVisibility != BuildVisibility.hidden){
  314                                image.save(block.name + "-icon-logic");
  315                            }
  316                        }
  317    
  318                        boolean hasEmpty = false;
  319                        Color average = new Color();
  320                        float asum = 0f;
  321                        for(int x = 0; x < image.width; x++){
  322                            for(int y = 0; y < image.height; y++){
  323                                Color color = image.getColor(x, y);
  324                                average.r += color.r*color.a;
  325                                average.g += color.g*color.a;
  326                                average.b += color.b*color.a;
  327                                asum += color.a;
  328                                if(color.a < 0.9f){
  329                                    hasEmpty = true;
  330                                }
      ...
```
Post-state:
```java
   37    public static void generate(){
   38            ObjectMap<Block, Image> gens = new ObjectMap<>();
   39    
   40            if(!paletteMap.isEmpty()){
   41                ImagePacker.generate("uipalette", () -> {
   42                    Fi.get("../ui").walk(fi -> {
   43                        if(!fi.extEquals("png")) return;
   44    
   45                        Pixmap pix = new Pixmap(fi);
   46                        pix.setBlending(Pixmap.Blending.sourceOver);
   47                        pix.each((x, y) -> {
   48                            int value = pix.getPixel(x, y);
   49                            pix.draw(x, y, paletteMap.get(value, value));
   50                        });
   51    
   52                        fi.writePNG(pix);
   53                    });
   54                });
   55            }
   56    
   57            ImagePacker.generate("splashes", () -> {
      ...
```

## Mindustry:de0235ad943e:0 — REMOVE_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/de0235ad943e790c36f7ec2db90d299c5b490d3e
- method: `Consumers.add(T)` in `core/src/io/anuke/mindustry/world/consumers/Consumers.java`
- removed statement (pre-state): `Log.warn("[WARN] Conflict: Replacing {0} with {1}", consume, map[consume.type().ordinal()])`
- levels: WARN -> None

Pre-state:
```java
   90    public <T extends Consume> T add(T consume){
   91            if(map[consume.type().ordinal()] != null){
   92 >>             Log.warn("[WARN] Conflict: Replacing {0} with {1}", consume, map[consume.type().ordinal()]);
   93            }
   94    
   95            map[consume.type().ordinal()] = consume;
   96            return consume;
   97        }
```
Post-state:
```java
   78    public <T extends Consume> T add(T consume){
   79            map[consume.type().ordinal()] = consume;
   80            return consume;
   81        }
```

## Mindustry:da19c5ae19dc:0 — REMOVE_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/da19c5ae19dcd47abca5143f4ea4794c414738f4
- method: `LStatements.WriteStatement.build(Table)` in `core/src/mindustry/logic/LStatements.java`
- removed statement (pre-state): `Log.info("mem:: ")`
- levels: INFO -> None

Pre-state:
```java
   19    @Override
   20            public void build(Table table){
   21 >>             Log.info("mem:: ");
   22    
   23                table.field(to, Styles.nodeField, str -> to = str)
   24                .size(100f, 40f).pad(2f).color(table.color);
   25    
   26                table.add(" = ");
   27    
   28                table.field(from, Styles.nodeField, str -> from = str)
   29                .size(100f, 40f).pad(2f).color(table.color);
   30            }
```
Post-state:
```java
   18    @Override
   19            public void build(Table table){
   20                field(table, to, str -> to = str);
   21    
   22                table.add(" = ");
   23    
   24                field(table, from, str -> from = str);
   25            }
```

## Mindustry:6566f1c5547e:1 — REMOVE_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/6566f1c5547e4ccd1e808ab92e5fb6d9bf5d9f16
- method: `ServerControl.setup(String[])` in `server/src/mindustry/server/ServerControl.java`
- removed statement (pre-state): `info("Game over! Team @ is victorious with @ players online on map @.", event.winner.name, Groups.player.size(), Strings.capitalize(state.map.plainName()))`
- levels: INFO -> None

Pre-state:
```java
      ...
  160    
  161            customMapDirectory.mkdirs();
  162    
  163            if(Version.build == -1){
  164                warn("&lyYour server is running a custom build, which means that client checking is disabled.");
  165                warn("&lyIt is highly advised to specify which version you're using by building with gradle args &lb&fb-Pbuildversion=&lr<build>");
  166            }
  167    
  168            //set up default shuffle mode
  169            try{
  170                maps.setShuffleMode(ShuffleMode.valueOf(Core.settings.getString("shufflemode")));
  171            }catch(Exception e){
  172                maps.setShuffleMode(ShuffleMode.all);
  173            }
  174    
  175            Events.on(GameOverEvent.class, event -> {
  176                if(inGameOverWait) return;
  177                if(state.rules.waves){
  178                    info("Game over! Reached wave @ with @ players online on map @.", state.wave, Groups.player.size(), Strings.capitalize(state.map.plainName()));
  179                }else{
  180 >>                 info("Game over! Team @ is victorious with @ players online on map @.", event.winner.name, Groups.player.size(), Strings.capitalize(state.map.plainName()));
  181                }
  182    
  183                //set next map to be played
  184                Map map = nextMapOverride != null ? nextMapOverride : maps.getNextMap(lastMode, state.map);
  185                nextMapOverride = null;
  186                if(map != null){
  187                    Call.infoMessage((state.rules.pvp
  188                    ? "[accent]The " + event.winner.coloredName() + " team is victorious![]\n" : "[scarlet]Game over![]\n")
  189                    + "\nNext selected map: [accent]" + map.name() + "[white]"
  190                    + (map.hasTag("author") ? " by[accent] " + map.author() + "[white]" : "") + "." +
  191                    "\nNew game begins in " + roundExtraTime + " seconds.");
  192    
  193                    state.gameOver = true;
  194                    Call.updateGameOver(event.winner);
  195    
  196                    info("Selected next map to be @.", map.plainName());
  197    
  198                    play(true, () -> world.loadMap(map, map.applyRules(lastMode)));
  199                }else{
  200                    netServer.kickAll(KickReason.gameover);
      ...
```
Post-state:
```java
  109    protected void setup(String[] args){
  110            Core.settings.defaults(
  111                "bans", "",
  112                "admins", "",
  113                "shufflemode", "custom",
  114                "globalrules", "{reactorExplosions: false, logicUnitBuild: false}"
  115            );
  116    
  117            //update log level
  118            Config.debug.set(Config.debug.bool());
  119    
  120            try{
  121                lastMode = Gamemode.valueOf(Core.settings.getString("lastServerMode", "survival"));
  122            }catch(Exception e){ //handle enum parse exception
  123                lastMode = Gamemode.survival;
  124            }
  125    
  126            logger = (level1, text) -> {
  127                //err has red text instead of reset.
  128                if(level1 == LogLevel.err) text = text.replace(reset, lightRed + bold);
  129    
      ...
```

## SkyHussars:ba4c645491c3:5 — REMOVE_LOG

- repo: SkyHussars  commit: https://github.com/ZoltanTheHun/SkyHussars/commit/ba4c645491c340544f8de5b47f0366c6a4f0fadb
- method: `AdvancedPlanePhysics.calculateAirfoilForces(Quaternion,Vector3f)` in `src/main/java/com/codebetyars/skyhussars/engine/physics/AdvancedPlanePhysics.java`
- removed statement (pre-state): `logger.debug("Airfoilforce points to: " + airfoilForce.toString())`
- levels: DEBUG -> None

Pre-state:
```java
  150    private ActingForces calculateAirfoilForces(Quaternion rotation, Vector3f vFlow) {
  151            Vector3f vLinearAcceleration = Vector3f.ZERO;
  152            Vector3f vTorque = Vector3f.ZERO;
  153            for (Airfoil airfoil : airfoils) {
  154                logger.debug("flow " + vFlow + ", rotation" + rotation + ", angular velocity " + vAngularVelocity);
  155                Vector3f airfoilForce = airfoil.calculateResultantForce(airDensity, vFlow, rotation, vAngularVelocity);
  156                logger.debug("Airfoilforce points to: " + airfoilForce.toString()/*.normalize().dot(situation.mult(Vector3f.UNIT_Y))*/);
  157                logger.debug("rotation" + rotation + ", linear" + vLinearAcceleration + ", airfoil " + airfoilForce);
  158                vLinearAcceleration = vLinearAcceleration.add(airfoilForce);
  159                airfoilForce = rotation.inverse().mult(airfoilForce);
  160                Vector3f distFromCenter = airfoil.getCenterOfGravity();
  161 >>             logger.debug("Airfoilforce points to: " + airfoilForce.toString());
  162                vTorque = vTorque.add(distFromCenter.cross(airfoilForce));
  163            }
  164            return new ActingForces(vLinearAcceleration, vTorque);
  165        }
```
Post-state:
```java
  150    private ActingForces calculateAirfoilForces(Quaternion rotation, Vector3f vFlow) {
  151            Vector3f vLinearAcceleration = Vector3f.ZERO;
  152            Vector3f vTorque = Vector3f.ZERO;
  153            for (Airfoil airfoil : airfoils) {
  154                Vector3f airfoilForce = airfoil.calculateResultantForce(airDensity, vFlow, rotation, vAngularVelocity);
  155                vLinearAcceleration = vLinearAcceleration.add(airfoilForce);
  156                airfoilForce = rotation.inverse().mult(airfoilForce);
  157                Vector3f distFromCenter = airfoil.getCenterOfGravity();
  158                vTorque = vTorque.add(distFromCenter.cross(airfoilForce));
  159            }
  160            return new ActingForces(vLinearAcceleration, vTorque);
  161        }
```

## Mindustry:d4d9d59fe43b:1 — REMOVE_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/d4d9d59fe43bb5533bad8667e0e96c6f19e53466
- method: `ServerControl.ServerControl(String[])` in `server/src/io/anuke/mindustry/server/ServerControl.java`
- removed statement (pre-state): `info("Re-trying sector map.")`
- levels: INFO -> None

Pre-state:
```java
      ...
   88    
   89                if(mode != ShuffleMode.off){
   90                    if(world.getSector() == null){
   91                        if(world.maps().all().size > 0){
   92                            Array<Map> maps = mode == ShuffleMode.both ? world.maps().all() :
   93                            mode == ShuffleMode.normal ? world.maps().defaultMaps() : world.maps().customMaps();
   94    
   95                            Map previous = world.getMap();
   96                            Map map = previous;
   97                            if(maps.size > 1){
   98                                while(map == previous) map = maps.random();
   99                            }
  100    
  101                            info("Selected next map to be {0}.", map.name);
  102    
  103                            logic.reset();
  104                            world.loadMap(map);
  105                            state.set(State.playing);
  106                        }
  107                    }else{
  108 >>                     info("Re-trying sector map.");
  109                        playSectorMap();
  110                    }
  111                }else{
  112                    state.set(State.menu);
  113                    Net.closeServer();
  114                }
  115            });
  116    
  117            info("&lcServer loaded. Type &ly'help'&lc for help.");
  118        }
```
Post-state:
```java
   44    public ServerControl(String[] args){
   45            Settings.defaultList(
   46                "shufflemode", "normal",
   47                "bans", "",
   48                "admins", "",
   49                "sector_x", 0,
   50                "sector_y", 1
   51            );
   52    
   53            mode = ShuffleMode.valueOf(Settings.getString("shufflemode"));
   54    
   55            Effects.setScreenShakeProvider((a, b) -> {});
   56            Effects.setEffectProvider((a, b, c, d, e, f) -> {});
   57            Sounds.setHeadless(true);
   58    
   59            registerCommands();
   60    
   61            Gdx.app.postRunnable(() -> {
   62                String[] commands = {};
   63    
   64                if(args.length > 0){
      ...
```

## OpenRTS:b8bb7ce553de:12 — REMOVE_LOG

- repo: OpenRTS  commit: https://github.com/methusalah/OpenRTS/commit/b8bb7ce553dece71b5a9a7ddfb37a76498532996
- method: `EditorInputInterpreter.registerInputs(InputManager)` in `core/src/controller/editor/EditorInputInterpreter.java`
- removed statement (pre-state): `LogUtil.logger.info("------ Lighting (numpad)")`
- levels: INFO -> None

Pre-state:
```java
      ...
  106    		inputManager.addMapping(DEC_INTENSITY, new KeyTrigger(KeyInput.KEY_SUBTRACT));
  107    		inputManager.addMapping(TOGGLE_SPEED, new KeyTrigger(KeyInput.KEY_NUMPAD9));
  108    		inputManager.addMapping(DEC_RED, new KeyTrigger(KeyInput.KEY_NUMPAD1));
  109    		inputManager.addMapping(DEC_GREEN, new KeyTrigger(KeyInput.KEY_NUMPAD2));
  110    		inputManager.addMapping(DEC_BLUE, new KeyTrigger(KeyInput.KEY_NUMPAD3));
  111    		inputManager.addMapping(RESET_COLOR, new KeyTrigger(KeyInput.KEY_NUMPAD0));
  112    		inputManager.addMapping(SAVE, new KeyTrigger(KeyInput.KEY_F5));
  113    		inputManager.addMapping(LOAD, new KeyTrigger(KeyInput.KEY_F9));
  114    		inputManager.addMapping(NEW, new KeyTrigger(KeyInput.KEY_F12));
  115    
  116    		inputManager.addListener(this, mappings);
  117    
  118    		LogUtil.logger.info("------ Map editing (ZQSD zone)");
  119    		LogUtil.logger.info(" Tools : '1' for cliff tool, '2' for height tool, '3' for atlas tool, '4' for ramp tool, '5' for unit tool.");
  120    		LogUtil.logger.info("          'e' toggle between actual tool's operations (raise, low, noise, smooth, propagate, uniform...");
  121    		LogUtil.logger.info("          'd' toggle between actual tool's sets (cliff styles, textures...)");
  122    		LogUtil.logger.info(" Pencil : 'a' toggle between pencil's shapes (square, diamond and circle)");
  123    		LogUtil.logger.info("          'z' toggle between pencil's modes (rough, brush and noise)");
  124    		LogUtil.logger.info("          'q' & 'w' increase/decrease radius");
  125    		LogUtil.logger.info("");
  126 >> 		LogUtil.logger.info("------ Lighting (numpad)");
  127    		LogUtil.logger.info(" '7' toggle between sunlight components : sunlight/shadowcaster/both/ambient");
  128    		LogUtil.logger.info(" '8' & '5' increase/decrease daytime");
  129    		LogUtil.logger.info(" '4' & '6' rotate compass");
  130    		LogUtil.logger.info(" '1', '2' & '3' decrease red, green and blue component");
  131    		LogUtil.logger.info(" '0' reset color");
  132    		LogUtil.logger.info(" '+' & '-' change intensity");
  133    		LogUtil.logger.info("");
  134    		LogUtil.logger.info("------- General");
  135    		LogUtil.logger.info("F5 to save, F9 to load, F12 for a new map");
  136    	}
```
Post-state:
```java
   77    @Override
   78    	protected void registerInputs(InputManager inputManager) {
   79    		inputManager.addMapping(SWITCH_CTRL_1, new KeyTrigger(KeyInput.KEY_F1));
   80    		inputManager.addMapping(SWITCH_CTRL_2, new KeyTrigger(KeyInput.KEY_F2));
   81    		inputManager.addMapping(SWITCH_CTRL_3, new KeyTrigger(KeyInput.KEY_F3));
   82    
   83    		inputManager.addMapping(PRIMARY_ACTION, new MouseButtonTrigger(0));
   84    		inputManager.addMapping(SECONDARY_ACTION, new MouseButtonTrigger(1));
   85    
   86    		inputManager.addMapping(TOGGLE_PENCIL_SHAPE, new KeyTrigger(KeyInput.KEY_A));
   87    		inputManager.addMapping(TOGGLE_PENCIL_MODE, new KeyTrigger(KeyInput.KEY_Z));
   88    		inputManager.addMapping(INC_SELECTOR_RADIUS, new KeyTrigger(KeyInput.KEY_Q));
   89    		inputManager.addMapping(DEC_SELECTOR_RADIUS, new KeyTrigger(KeyInput.KEY_W));
   90    		inputManager.addMapping(SET_CLIFF_TOOL, new KeyTrigger(KeyInput.KEY_1));
   91    		inputManager.addMapping(SET_HEIGHT_TOOL, new KeyTrigger(KeyInput.KEY_2));
   92    		inputManager.addMapping(SET_ATLAS_TOOL, new KeyTrigger(KeyInput.KEY_3));
   93    		inputManager.addMapping(SET_RAMP_TOOL, new KeyTrigger(KeyInput.KEY_4));
   94    		inputManager.addMapping(SET_UNIT_TOOL, new KeyTrigger(KeyInput.KEY_5));
   95    
   96    		inputManager.addMapping(TOGGLE_GRID, new KeyTrigger(KeyInput.KEY_G));
   97    		inputManager.addMapping(TOGGLE_OPERATION, new KeyTrigger(KeyInput.KEY_E));
      ...
```

## Mindustry:64533de59724:0 — REMOVE_LOG

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/64533de59724eedf9225bc1e114740fe3e97dcf4
- method: `Block.init()` in `core/src/io/anuke/mindustry/world/Block.java`
- removed statement (pre-state): `Log.warn("No name for block '{0}' found. Add the following to bundle.properties:\nblock.{0}.name = {1}", name, Strings.capitalize(name))`
- levels: WARN -> None

Pre-state:
```java
  271    @Override
  272        public void init(){
  273            //initialize default health based on size
  274            if(health == -1){
  275                health = size * size * 40;
  276            }
  277    
  278            buildCost = 0f;
  279            for(ItemStack stack : buildRequirements){
  280                buildCost += stack.amount * stack.item.cost;
  281            }
  282    
  283            setStats();
  284            setBars();
  285    
  286            consumes.checkRequired(this);
  287    
  288            if(buildRequirements.length > 0 && !Core.bundle.has("block." + name + ".name")){
  289 >>             Log.warn("No name for block '{0}' found. Add the following to bundle.properties:\nblock.{0}.name = {1}", name, Strings.capitalize(name));
  290            }
  291        }
```
Post-state:
```java
  271    @Override
  272        public void init(){
  273            //initialize default health based on size
  274            if(health == -1){
  275                health = size * size * 40;
  276            }
  277    
  278            buildCost = 0f;
  279            for(ItemStack stack : buildRequirements){
  280                buildCost += stack.amount * stack.item.cost;
  281            }
  282    
  283            setStats();
  284            setBars();
  285    
  286            consumes.checkRequired(this);
  287        }
```

## SkyHussars:e01e0ab68a9d:0 — REMOVE_LOG

- repo: SkyHussars  commit: https://github.com/ZoltanTheHun/SkyHussars/commit/e01e0ab68a9dc60b65f7886bfcff32b425de55e3
- method: `ProjectileManager.update(float)` in `src/main/java/com/codebetyars/skyhussars/engine/weapons/ProjectileManager.java`
- removed statement (pre-state): `logger.info("Current projectiles: {}", projectileGeometries.size())`
- levels: INFO -> None

Pre-state:
```java
   67    public void update(float tpf) {
   68 >>         logger.info("Current projectiles: {}", projectileGeometries.size());
   69            Iterator<Geometry > geomIterator = projectileGeometries.iterator();
   70            projectiles.parallelStream().forEach(projectile -> projectile.update(tpf));
   71            Iterator<Projectile> it = projectiles.iterator();
   72            while (it.hasNext()) {
   73                Projectile projectile = it.next();
   74                if (!projectile.isLive()) {
   75                    it.remove();
   76                    if (geomIterator.hasNext()) {
   77                        Geometry geom = geomIterator.next();
   78                        rootNode.detachChild(geom);
   79                        geomIterator.remove();
   80                    }
   81                } else {
   82                    if (geomIterator.hasNext()) {
   83                        Geometry geom = geomIterator.next();
   84                        geom.setLocalTranslation(projectile.getLocation());
   85                        Vector3f direction = projectile.getVelocity().normalize();
   86                        geom.lookAt(direction, Vector3f.UNIT_Y);
   87                    }
   88                }
      ...
```
Post-state:
```java
   67    public void update(float tpf) {
   68            Iterator<Geometry > geomIterator = projectileGeometries.iterator();
   69            projectiles.parallelStream().forEach(projectile -> projectile.update(tpf));
   70            Iterator<Projectile> it = projectiles.iterator();
   71            while (it.hasNext()) {
   72                Projectile projectile = it.next();
   73                if (!projectile.isLive()) {
   74                    it.remove();
   75                    if (geomIterator.hasNext()) {
   76                        Geometry geom = geomIterator.next();
   77                        rootNode.detachChild(geom);
   78                        geomIterator.remove();
   79                    }
   80                } else {
   81                    if (geomIterator.hasNext()) {
   82                        Geometry geom = geomIterator.next();
   83                        geom.setLocalTranslation(projectile.getLocation());
   84                        Vector3f direction = projectile.getVelocity().normalize();
   85                        geom.lookAt(direction, Vector3f.UNIT_Y);
   86                    }
   87                }
      ...
```

## riiablo:5d51a1c160f4:4 — REMOVE_LOG

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/5d51a1c160f4c971de28b466832f9f2ab422537c
- method: `NetworkSynchronizer.sync(int,Sync)` in `server/d2gs/src/com/riiablo/server/d2gs/NetworkSynchronizer.java`
- removed statement (pre-state): `Gdx.app.log(TAG, "  " + velocity)`
- levels: INFO -> None

Pre-state:
```java
      ...
  152              CofAlphasP data = (CofAlphasP) sync.data(new CofAlphasP(), i);
  153              for (int j = 0, s = data.alphaLength(); j < s; j++) {
  154                alpha[j] = data.alpha(j);
  155              }
  156              Gdx.app.log(TAG, "  " + Arrays.toString(alpha));
  157              break;
  158            }
  159            case SyncData.PositionP: {
  160              Vector2 position = mPosition.get(entityId).position;
  161              PositionP data = (PositionP) sync.data(new PositionP(), i);
  162              position.x = data.x();
  163              position.y = data.y();
  164              Gdx.app.log(TAG, "  " + position);
  165              break;
  166            }
  167            case SyncData.VelocityP: {
  168              Vector2 velocity = mVelocity.get(entityId).velocity;
  169              VelocityP data = (VelocityP) sync.data(new VelocityP(), i);
  170              velocity.x = data.x();
  171              velocity.y = data.y();
  172 >>           Gdx.app.log(TAG, "  " + velocity);
  173              break;
  174            }
  175            case SyncData.AngleP: {
  176              Vector2 angle = mAngle.get(entityId).target;
  177              AngleP data = (AngleP) sync.data(new AngleP(), i);
  178              angle.x = data.x();
  179              angle.y = data.y();
  180              Gdx.app.log(TAG, "  " + angle);
  181              break;
  182            }
  183            default:
  184              Gdx.app.error(TAG, "Unknown packet type: " + SyncData.name(sync.dataType(i)));
  185          }
  186        }
  187      }
```
Post-state:
```java
   46    public void sync(int entityId, D2GS packet) {
   47        Gdx.app.log(TAG, "syncing " + entityId);
   48        serializer.deserialize(entityId, packet);
   49      }
```

## riiablo:5d51a1c160f4:6 — REMOVE_LOG

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/5d51a1c160f4c971de28b466832f9f2ab422537c
- method: `NetworkSynchronizer.sync(int,Sync)` in `server/d2gs/src/com/riiablo/server/d2gs/NetworkSynchronizer.java`
- removed statement (pre-state): `Gdx.app.error(TAG, "Unknown packet type: " + SyncData.name(sync.dataType(i)))`
- levels: ERROR -> None

Pre-state:
```java
      ...
  164              Gdx.app.log(TAG, "  " + position);
  165              break;
  166            }
  167            case SyncData.VelocityP: {
  168              Vector2 velocity = mVelocity.get(entityId).velocity;
  169              VelocityP data = (VelocityP) sync.data(new VelocityP(), i);
  170              velocity.x = data.x();
  171              velocity.y = data.y();
  172              Gdx.app.log(TAG, "  " + velocity);
  173              break;
  174            }
  175            case SyncData.AngleP: {
  176              Vector2 angle = mAngle.get(entityId).target;
  177              AngleP data = (AngleP) sync.data(new AngleP(), i);
  178              angle.x = data.x();
  179              angle.y = data.y();
  180              Gdx.app.log(TAG, "  " + angle);
  181              break;
  182            }
  183            default:
  184 >>           Gdx.app.error(TAG, "Unknown packet type: " + SyncData.name(sync.dataType(i)));
  185          }
  186        }
  187      }
```
Post-state:
```java
   46    public void sync(int entityId, D2GS packet) {
   47        Gdx.app.log(TAG, "syncing " + entityId);
   48        serializer.deserialize(entityId, packet);
   49      }
```

## OpenKeeper:003dd71f76a9:1 — REMOVE_LOG

- repo: OpenKeeper  commit: https://github.com/tonihele/OpenKeeper/commit/003dd71f76a975df368e22313400c98614388f8c
- method: `GameLogicManager.processTick(long)` in `src/toniarts/openkeeper/game/logic/GameLogicManager.java`
- removed statement (pre-state): `logger.log(tickTime < delta ? Level.TRACE : Level.ERROR, "Tick took {0} ms!", TimeUnit.MILLISECONDS.convert(tickTime, TimeUnit.NANOSECONDS))`
- levels: None -> None

Pre-state:
```java
   48    @Override
   49        public void processTick(long delta) {
   50    
   51            // Update game time
   52            long start = System.nanoTime();
   53            float tpf = delta / 1000000000f;
   54    
   55            // Update updatables
   56            for (IGameLogicUpdatable updatable : updatables) {
   57                try {
   58                    updatable.processTick(tpf, timeElapsed);
   59                } catch (Exception e) {
   60                    logger.log(Level.ERROR, "Error in game logic tick on " + updatable.getClass() + "!", e);
   61                }
   62            }
   63    
   64            // Logging
   65            long tickTime = System.nanoTime() - start;
   66 >>         logger.log(tickTime < delta ? Level.TRACE : Level.ERROR, "Tick took {0} ms!", TimeUnit.MILLISECONDS.convert(tickTime, TimeUnit.NANOSECONDS));
   67    
   68            // Increase ticks & time
   69            timeElapsed += tpf;
   70            ticks++;
   71        }
```
Post-state:
```java
   44    @Override
   45        public void processTick(float tpf) {
   46            // Update updatables
   47            for (IGameLogicUpdatable updatable : updatables) {
   48                try {
   49                    updatable.processTick(tpf);
   50                } catch (Exception e) {
   51                    logger.log(Level.ERROR, "Error in game logic tick on " + updatable.getClass() + "!", e);
   52                }
   53            }
   54        }
```

## subspace-infinity:71214a895762:0 — CHANGE_LEVEL

- repo: subspace-infinity  commit: https://github.com/assofohdz/subspace-infinity/commit/71214a895762e28c4f4ee8b81d184eec9352d67d
- method: `ConnectState.ConnectionObserver.clientConnected(Client)` in `sim-eth-basic/src/main/java/example/ConnectState.java`
- statement: `log.trace("clientConnected(" + c + ")")` -> `log.info("clientConnected(" + c + ")")`
- levels: TRACE -> INFO

Pre-state:
```java
  207    public void clientConnected( final Client c ) {
  208 >>             log.trace("clientConnected(" + c + ")");
  209                getApplication().enqueue(new Callable() {
  210                        public Object call() {
  211                            connected();
  212                            return null;
  213                        }
  214                    });
  215            }
```
Post-state:
```java
  207    public void clientConnected( final Client c ) {
  208 >>             log.info("clientConnected(" + c + ")");
  209                getApplication().enqueue(new Callable() {
  210                        public Object call() {
  211                            connected();
  212                            return null;
  213                        }
  214                    });
  215            }
```

## riiablo:c12747500748:9 — CHANGE_LEVEL

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/c127475007483b9c27634787fbf894500c509938
- method: `StatList.add(int,short,StatList,int)` in `core/src/com/riiablo/attributes/StatList.java`
- statement: `log.info(indexDebugString(index))` -> `log.debug(indexDebugString(index))`
- levels: INFO -> DEBUG

Pre-state:
```java
  274    public int add(int list, short stat, StatList src, int srcList) {
  275        assertMutable();
  276        log.traceEntry("add(list: {}, stat: {}, src: {}, srcList: {})", list, stat, src, srcList);
  277        assert !Stat.hasParams(stat) : "stat(" + stat + ") requires params";
  278        assert encoding(stat) <= 2 : "#add() unsupported for encoding(" + encoding(stat) + ")";
  279        final int index = indexOf(list, stat, 0);
  280        final int otherIndex = src.indexOf(srcList, stat, 0);
  281        if (log.debugEnabled()) log.debug(
  282            "add(stat: {} ({}), this: {}, src: {})",
  283            stat, entry(stat), index >= 0 ? asString(index) : "null", src.asString(otherIndex));
  284        if (index >= 0 && ids[index] == stat) {
  285          values[index] += src.values[otherIndex];
  286 >>       if (log.infoEnabled()) log.info(indexDebugString(index));
  287          return index;
  288        } else {
  289          /** TODO: possibility to speed this up with {@link #insertAt} */
  290          final int putIndex = put(list, stat, src.values[otherIndex]);
  291          assert putIndex == ~index : "index(" + putIndex + ") != expected index(" + ~index + ")";
  292          return putIndex;
  293        }
  294        // max
  295      }
```
Post-state:
```java
  227    public int add(final int list, final short stat, final StatList src, final int srcList) {
  228        if (log.traceEnabled()) log.traceEntry("add(list: {}, stat: {}, src: {}, srcList: {})", list, stat, src, srcList);
  229        assertMutable();
  230        assert !Stat.hasParams(stat) : "stat(" + stat + ") requires params";
  231        assert encoding(stat) <= 2 : "#add() unsupported for encoding(" + encoding(stat) + ")";
  232        final int index = indexOf(list, stat, 0);
  233        final int otherIndex = src.indexOf(srcList, stat, 0);
  234        if (log.traceEnabled()) log.trace(
  235            "add(stat: {} ({}), this: {}, src: {})",
  236            stat, entry(stat), index >= 0 ? asString(index) : "null", src.asString(otherIndex));
  237        if (index >= 0 && ids[index] == stat) {
  238          values[index] += src.values[otherIndex];
  239 >>       if (log.debugEnabled()) log.debug(indexDebugString(index));
  240          return index;
  241        } else {
  242          /** TODO: possibility to speed this up with {@link #insertAt} */
  243          final int putIndex = put(list, stat, src.values[otherIndex]);
  244          assert putIndex == ~index : "index(" + putIndex + ") != expected index(" + ~index + ")";
  245          return putIndex;
  246        }
  247        // max
  248      }
```

## subspace-infinity:1cb77ff9cb02:8 — CHANGE_LEVEL

- repo: subspace-infinity  commit: https://github.com/assofohdz/subspace-infinity/commit/1cb77ff9cb02c6ec8c42a68ee34767156ce08803
- method: `GameServer.logStats()` in `subspace-infinity/src/main/java/infinity/net/server/GameServer.java`
- statement: `log.info("Client[" + conn.getId() + "] address:" + conn.getAddress())` -> `log.debug("Client[" + conn.getId() + "] address:" + conn.getAddress())`
- levels: INFO -> DEBUG

Pre-state:
```java
  344    public void logStats() {
  345    
  346            EtherealHost host = server.getServices().getService(EtherealHost.class);
  347    
  348            for (HostedConnection conn : server.getConnections()) {
  349 >>             log.info("Client[" + conn.getId() + "] address:" + conn.getAddress());
  350                NetworkStateListener listener = host.getStateListener(conn);
  351                if (listener == null) {
  352                    log.info("[" + conn.getId() + "] No stats");
  353                    continue;
  354                }
  355                log.info("[" + conn.getId() + "] Ping time: " + (listener.getConnectionStats().getAveragePingTime() / 1000000.0) + " ms");
  356                String miss = String.format("%.02f", listener.getConnectionStats().getAckMissPercent());
  357                log.info("[" + conn.getId() + "] Ack miss: " + miss + "%");
  358                log.info("[" + conn.getId() + "] Average msg size: " + listener.getConnectionStats().getAverageMessageSize() + " bytes");
  359            }
  360        }
```
Post-state:
```java
  344    public void logStats() {
  345    
  346            EtherealHost host = server.getServices().getService(EtherealHost.class);
  347    
  348            for (HostedConnection conn : server.getConnections()) {
  349 >>             log.debug("Client[" + conn.getId() + "] address:" + conn.getAddress());
  350                NetworkStateListener listener = host.getStateListener(conn);
  351                if (listener == null) {
  352                    log.info("[" + conn.getId() + "] No stats");
  353                    continue;
  354                }
  355                log.debug("[" + conn.getId() + "] Ping time: " + (listener.getConnectionStats().getAveragePingTime() / 1000000.0) + " ms");
  356                String miss = String.format("%.02f", listener.getConnectionStats().getAckMissPercent());
  357                log.debug("[" + conn.getId() + "] Ack miss: " + miss + "%");
  358                log.debug("[" + conn.getId() + "] Average msg size: " + listener.getConnectionStats().getAverageMessageSize() + " bytes");
  359            }
  360        }
```

## riiablo:090edf78e214:1 — CHANGE_LEVEL

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/090edf78e214b5dcedee3ed20bb52d328821d4f3
- method: `Actioneer.onAnimDataFinished(AnimDataFinishedEvent)` in `core/src/com/riiablo/engine/server/Actioneer.java`
- statement: `log.debug("onAnimDataFinished: {}", event.entityId)` -> `log.traceEntry("onAnimDataFinished(entityId: {})", event.entityId)`
- levels: DEBUG -> TRACE

Pre-state:
```java
   92    @Subscribe
   93      public void onAnimDataFinished(AnimDataFinishedEvent event) {
   94        if (!mCasting.has(event.entityId)) return;
   95 >>     log.debug("onAnimDataFinished: {}", event.entityId);
   96        mCasting.remove(event.entityId);
   97      }
```
Post-state:
```java
   91    @Subscribe
   92      public void onAnimDataFinished(AnimDataFinishedEvent event) {
   93        if (!mCasting.has(event.entityId)) return;
   94 >>     log.traceEntry("onAnimDataFinished(entityId: {})", event.entityId);
   95        mCasting.remove(event.entityId);
   96      }
```

## riiablo:090edf78e214:0 — CHANGE_LEVEL

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/090edf78e214b5dcedee3ed20bb52d328821d4f3
- method: `Actioneer.onAnimDataKeyframe(AnimDataKeyframeEvent)` in `core/src/com/riiablo/engine/server/Actioneer.java`
- statement: `log.debug("onAnimDataKeyframe: {}, {} ({})", event.entityId, event.keyframe, Engine.getKeyframe(event.keyframe))` -> `log.traceEntry("onAnimDataKeyframe(entityId: {}, keyframe: {} ({}))", event.entityId, event.keyframe, Engine.getKeyframe(event.keyframe))`
- levels: DEBUG -> TRACE

Pre-state:
```java
   82    @Subscribe
   83      public void onAnimDataKeyframe(AnimDataKeyframeEvent event) {
   84        if (!mCasting.has(event.entityId)) return;
   85 >>     log.debug("onAnimDataKeyframe: {}, {} ({})", event.entityId, event.keyframe, Engine.getKeyframe(event.keyframe));
   86        final Casting casting = mCasting.get(event.entityId);
   87        final Skills.Entry skill = Riiablo.files.skills.get(casting.skillId);
   88        srvdofunc(event.entityId, skill.srvdofunc, casting.target);
   89        events.dispatch(SkillDoEvent.obtain(event.entityId, casting.skillId, skill.srvdofunc, skill.cltdofunc));
   90      }
```
Post-state:
```java
   81    @Subscribe
   82      public void onAnimDataKeyframe(AnimDataKeyframeEvent event) {
   83        if (!mCasting.has(event.entityId)) return;
   84 >>     log.traceEntry("onAnimDataKeyframe(entityId: {}, keyframe: {} ({}))", event.entityId, event.keyframe, Engine.getKeyframe(event.keyframe));
   85        final Casting casting = mCasting.get(event.entityId);
   86        final Skills.Entry skill = Riiablo.files.skills.get(casting.skillId);
   87        srvdofunc(event.entityId, skill.srvdofunc, casting.target);
   88        events.dispatch(SkillDoEvent.obtain(event.entityId, casting.skillId, skill.srvdofunc, skill.cltdofunc));
   89      }
```

## OpenKeeper:6d54e8f8c02f:11 — CHANGE_LEVEL

- repo: OpenKeeper  commit: https://github.com/tonihele/OpenKeeper/commit/6d54e8f8c02f69e89a95555610d0652b2f4d4c2b
- method: `GameHostedService.stopHostingOnConnection(HostedConnection)` in `src/toniarts/openkeeper/game/network/game/GameHostedService.java`
- statement: `logger.log(Level.TRACE, "stopHostingOnConnection({0})", conn)` -> `logger.log(Level.DEBUG, "stopHostingOnConnection({0})", conn)`
- levels: TRACE -> DEBUG

Pre-state:
```java
  141    @Override
  142        public void stopHostingOnConnection(HostedConnection conn) {
  143 >>         logger.log(Level.TRACE, "stopHostingOnConnection({0})", conn);
  144            GameSessionImpl player = getGameSession(conn);
  145            if (player != null) {
  146    
  147                // Then we are still hosting on the connection... it's
  148                // possible that stopHostingOnConnection() is called more than
  149                // once for a particular connection since some other game code
  150                // may call it and it will also be called during connection shutdown.
  151                conn.setAttribute(ATTRIBUTE_SESSION, null);
  152    
  153                // Remove player session from the active sessions list
  154                players.remove(player.clientInfo);
  155                playersByConnection.remove(conn);
  156                playersInTransition.remove(player.clientInfo);
  157            }
  158        }
```
Post-state:
```java
  141    @Override
  142        public void stopHostingOnConnection(HostedConnection conn) {
  143 >>         logger.log(Level.DEBUG, "stopHostingOnConnection({0})", conn);
  144            GameSessionImpl player = getGameSession(conn);
  145            if (player != null) {
  146    
  147                // Then we are still hosting on the connection... it's
  148                // possible that stopHostingOnConnection() is called more than
  149                // once for a particular connection since some other game code
  150                // may call it and it will also be called during connection shutdown.
  151                conn.setAttribute(ATTRIBUTE_SESSION, null);
  152    
  153                // Remove player session from the active sessions list
  154                players.remove(player.clientInfo);
  155                playersByConnection.remove(conn);
  156                playersInTransition.remove(player.clientInfo);
  157            }
  158        }
```

## Mindustry:78fb4271205e:0 — CHANGE_LEVEL

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/78fb4271205e5c3b0a4675356248e2ce9217112f
- method: `.onUserStatsReceived(long,SteamID,SteamResult)` in `desktop/src/mindustry/desktop/steam/SStats.java`
- statement: `Log.err("Recieved steam stats.")` -> `Log.info("Recieved steam stats.")`
- levels: ERROR -> INFO

Pre-state:
```java
  279    @Override
  280        public void onUserStatsReceived(long gameID, SteamID steamID, SteamResult result){
  281            registerEvents();
  282    
  283            if(result != SteamResult.OK){
  284                Log.err("Failed to recieve steam stats: {0}", result);
  285            }else{
  286 >>             Log.err("Recieved steam stats.");
  287            }
  288        }
```
Post-state:
```java
  279    @Override
  280        public void onUserStatsReceived(long gameID, SteamID steamID, SteamResult result){
  281            registerEvents();
  282    
  283            if(result != SteamResult.OK){
  284                Log.err("Failed to recieve steam stats: {0}", result);
  285            }else{
  286 >>             Log.info("Recieved steam stats.");
  287            }
  288        }
```

## riiablo:f60040a5d2ee:15 — CHANGE_LEVEL

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/f60040a5d2eedfce53b0f84619b21f1c67adda8a
- method: `Excel.loadTxt(T,TxtParser)` in `core/src/main/java/com/riiablo/excel/Excel.java`
- statement: `Gdx.app.debug(TAG, String.format("Entry[%d](%s).%s=%s", i, name, field.getName(), Arrays.toString(value)))` -> `log.trace("Entry[{}]({}).{}={}", i, name, field.getName(), Arrays.toString(value))`
- levels: DEBUG -> TRACE

Pre-state:
```java
      ...
  251              if (DEBUG_ENTRIES) Gdx.app.debug(TAG, String.format("Entry[%d](%s).%s=%s", i, name, field.getName(), value));
  252            } else if (type == short[].class) {
  253              short[] value = parser.getShort(columnIds);
  254              field.set(entry, value);
  255              if (DEBUG_ENTRIES) Gdx.app.debug(TAG, String.format("Entry[%d](%s).%s=%s", i, name, field.getName(), Arrays.toString(value)));
  256            } else if (type == int.class) {
  257              int value = parser.getInt(columnIds[0]);
  258              field.setInt(entry, value);
  259              if (DEBUG_ENTRIES) Gdx.app.debug(TAG, String.format("Entry[%d](%s).%s=%s", i, name, field.getName(), value));
  260            } else if (type == int[].class) {
  261              int[] value = parser.getInt(columnIds);
  262              field.set(entry, value);
  263              if (DEBUG_ENTRIES) Gdx.app.debug(TAG, String.format("Entry[%d](%s).%s=%s", i, name, field.getName(), Arrays.toString(value)));
  264            } else if (type == long.class) {
  265              long value = parser.getLong(columnIds[0]);
  266              field.setLong(entry, value);
  267              if (DEBUG_ENTRIES) Gdx.app.debug(TAG, String.format("Entry[%d](%s).%s=%s", i, name, field.getName(), value));
  268            } else if (type == long[].class) {
  269              long[] value = parser.getLong(columnIds);
  270              field.set(entry, value);
  271 >>           if (DEBUG_ENTRIES) Gdx.app.debug(TAG, String.format("Entry[%d](%s).%s=%s", i, name, field.getName(), Arrays.toString(value)));
  272            } else if (type == boolean.class) {
  273              boolean value = parser.getBoolean(columnIds[0]);
  274              field.setBoolean(entry, value);
  275              if (DEBUG_ENTRIES) Gdx.app.debug(TAG, String.format("Entry[%d](%s).%s=%s", i, name, field.getName(), value));
  276            } else if (type == boolean[].class) {
  277              boolean[] value = parser.getBoolean(columnIds);
  278              field.set(entry, value);
  279              if (DEBUG_ENTRIES) Gdx.app.debug(TAG, String.format("Entry[%d](%s).%s=%s", i, name, field.getName(), Arrays.toString(value)));
  280            } else {
  281              throw new UnsupportedOperationException("No support for " + type + " fields");
  282            }
  283          }
  284    
  285          putIndex(primaryKey, primaryKeyType, i++, index, excel, entry);
  286        }
  287    
  288        return excel;
  289      }
```
Post-state:
```java
      ...
  257              if (DEBUG_ENTRIES) log.trace("Entry[{}]({}).{}={}", i, name, field.getName(), value);
  258            } else if (type == short[].class) {
  259              short[] value = parser.getShort(columnIds);
  260              field.set(entry, value);
  261              if (DEBUG_ENTRIES) log.trace("Entry[{}]({}).{}={}", i, name, field.getName(), Arrays.toString(value));
  262            } else if (type == int.class) {
  263              int value = parser.getInt(columnIds[0]);
  264              field.setInt(entry, value);
  265              if (DEBUG_ENTRIES) log.trace("Entry[{}]({}).{}={}", i, name, field.getName(), value);
  266            } else if (type == int[].class) {
  267              int[] value = parser.getInt(columnIds);
  268              field.set(entry, value);
  269              if (DEBUG_ENTRIES) log.trace("Entry[{}]({}).{}={}", i, name, field.getName(), Arrays.toString(value));
  270            } else if (type == long.class) {
  271              long value = parser.getLong(columnIds[0]);
  272              field.setLong(entry, value);
  273              if (DEBUG_ENTRIES) log.trace("Entry[{}]({}).{}={}", i, name, field.getName(), value);
  274            } else if (type == long[].class) {
  275              long[] value = parser.getLong(columnIds);
  276              field.set(entry, value);
  277 >>           if (DEBUG_ENTRIES) log.trace("Entry[{}]({}).{}={}", i, name, field.getName(), Arrays.toString(value));
  278            } else if (type == boolean.class) {
  279              boolean value = parser.getBoolean(columnIds[0]);
  280              field.setBoolean(entry, value);
  281              if (DEBUG_ENTRIES) log.trace("Entry[{}]({}).{}={}", i, name, field.getName(), value);
  282            } else if (type == boolean[].class) {
  283              boolean[] value = parser.getBoolean(columnIds);
  284              field.set(entry, value);
  285              if (DEBUG_ENTRIES) log.trace("Entry[{}]({}).{}={}", i, name, field.getName(), Arrays.toString(value));
  286            } else {
  287              throw new UnsupportedOperationException("No support for " + type + " fields");
  288            }
  289          }
  290    
  291          putIndex(primaryKey, primaryKeyType, i++, index, excel, entry);
  292        }
  293    
  294        return excel;
  295      }
```

## Mindustry:d8cd07127c0d:0 — CHANGE_LEVEL

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/d8cd07127c0d476e964b8731723b77fdd56817df
- method: `.loadScripts()` in `core/src/mindustry/mod/Mods.java`
- statement: `Log.debug("Time to initialize modded scripts: @", Time.elapsed())` -> `Log.info("Time to initialize modded scripts: @", Time.elapsed())`
- levels: DEBUG -> INFO

Pre-state:
```java
      ...
  437                            try{
  438                                if(scripts == null){
  439                                    scripts = platform.createScripts();
  440                                }
  441                                scripts.run(mod, main);
  442                            }catch(Throwable e){
  443                                Core.app.post(() -> {
  444                                    Log.err("Error loading main script @ for mod @.", main.name(), mod.meta.name);
  445                                    Log.err(e);
  446                                });
  447                            }
  448                        }else{
  449                            Core.app.post(() -> Log.err("No main.js found for mod @.", mod.meta.name));
  450                        }
  451                    }
  452                });
  453            }finally{
  454                content.setCurrentMod(null);
  455            }
  456    
  457 >>         Log.debug("Time to initialize modded scripts: @", Time.elapsed());
  458        }
```
Post-state:
```java
      ...
  437                            try{
  438                                if(scripts == null){
  439                                    scripts = platform.createScripts();
  440                                }
  441                                scripts.run(mod, main);
  442                            }catch(Throwable e){
  443                                Core.app.post(() -> {
  444                                    Log.err("Error loading main script @ for mod @.", main.name(), mod.meta.name);
  445                                    Log.err(e);
  446                                });
  447                            }
  448                        }else{
  449                            Core.app.post(() -> Log.err("No main.js found for mod @.", mod.meta.name));
  450                        }
  451                    }
  452                });
  453            }finally{
  454                content.setCurrentMod(null);
  455            }
  456    
  457 >>         Log.info("Time to initialize modded scripts: @", Time.elapsed());
  458        }
```

## Mindustry:e23119e33033:3 — CHANGE_LEVEL

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/e23119e3303314b279a4961aa371dc9d7971fa6a
- method: `EntityProcess.process(RoundEnvironment)` in `annotations/src/main/java/mindustry/annotations/impl/EntityProcess.java`
- statement: `Log.info("")` -> `Log.debug("")`
- levels: INFO -> DEBUG

Pre-state:
```java
      ...
  136                            .addAnnotations(Array.with(field.annotations())
  137                            .select(a -> a.toString().contains("Null")).map(AnnotationSpec::get)).build()).build());
  138                        }
  139                    }
  140    
  141                    write(inter);
  142    
  143                    //LOGGING
  144    
  145                    Log.info("&gGenerating interface for " + component.name());
  146    
  147                    for(TypeName tn : inter.superinterfaces){
  148                        Log.info("&g> &lbextends {0}", simpleName(tn.toString()));
  149                    }
  150    
  151                    //log methods generated
  152                    for(MethodSpec spec : inter.methodSpecs){
  153                        Log.info("&g> > &c{0} {1}({2})", simpleName(spec.returnType.toString()), spec.name, Array.with(spec.parameters).toString(", ", p -> simpleName(p.type.toString()) + " " + p.name));
  154                    }
  155    
  156 >>                 Log.info("");
  157                }
  158    
  159                //generate special render layer interfaces
  160                for(DrawLayer layer : DrawLayer.values()){
  161                    //create the DrawLayer interface that entities need to implement
  162                    String name = "DrawLayer" + Strings.capitalize(layer.name()) + "c";
  163                    TypeSpec.Builder inter = TypeSpec.interfaceBuilder(name)
  164                    .addSuperinterface(tname(packageName + ".Entityc"))
  165                    .addModifiers(Modifier.PUBLIC).addAnnotation(EntityInterface.class);
  166                    inter.addMethod(MethodSpec.methodBuilder("draw" + Strings.capitalize(layer.name())).addModifiers(Modifier.PUBLIC, Modifier.ABSTRACT).build());
  167                    write(inter);
  168                }
  169            }
```
Post-state:
```java
      ...
  136                            .addAnnotations(Array.with(field.annotations())
  137                            .select(a -> a.toString().contains("Null")).map(AnnotationSpec::get)).build()).build());
  138                        }
  139                    }
  140    
  141                    write(inter);
  142    
  143                    //LOGGING
  144    
  145                    Log.debug("&gGenerating interface for " + component.name());
  146    
  147                    for(TypeName tn : inter.superinterfaces){
  148                        Log.debug("&g> &lbextends {0}", simpleName(tn.toString()));
  149                    }
  150    
  151                    //log methods generated
  152                    for(MethodSpec spec : inter.methodSpecs){
  153                        Log.debug("&g> > &c{0} {1}({2})", simpleName(spec.returnType.toString()), spec.name, Array.with(spec.parameters).toString(", ", p -> simpleName(p.type.toString()) + " " + p.name));
  154                    }
  155    
  156 >>                 Log.debug("");
  157                }
  158    
  159                //generate special render layer interfaces
  160                for(DrawLayer layer : DrawLayer.values()){
  161                    //create the DrawLayer interface that entities need to implement
  162                    String name = "DrawLayer" + Strings.capitalize(layer.name()) + "c";
  163                    TypeSpec.Builder inter = TypeSpec.interfaceBuilder(name)
  164                    .addSuperinterface(tname(packageName + ".Entityc"))
  165                    .addModifiers(Modifier.PUBLIC).addAnnotation(EntityInterface.class);
  166                    inter.addMethod(MethodSpec.methodBuilder("draw" + Strings.capitalize(layer.name())).addModifiers(Modifier.PUBLIC, Modifier.ABSTRACT).build());
  167                    write(inter);
  168                }
  169            }
```

## Mindustry:19239a6890f2:0 — CHANGE_LEVEL

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/19239a6890f2d26368ca181d33fd0eb7dede3ae6
- method: `FloorRenderer.clearTiles()` in `core/src/mindustry/graphics/FloorRenderer.java`
- statement: `Log.info("Time to cache: {0}", Time.elapsed())` -> `Log.debug("Time to cache: {0}", Time.elapsed())`
- levels: INFO -> DEBUG

Pre-state:
```java
  224    public void clearTiles(){
  225            if(cbatch != null) cbatch.dispose();
  226    
  227            recacheSet.clear();
  228            int chunksx = Mathf.ceil((float)(world.width()) / chunksize),
  229            chunksy = Mathf.ceil((float)(world.height()) / chunksize);
  230            cache = new Chunk[chunksx][chunksy];
  231            cbatch = new MultiCacheBatch(chunksize * chunksize * 5);
  232    
  233            Time.mark();
  234    
  235            for(int x = 0; x < chunksx; x++){
  236                for(int y = 0; y < chunksy; y++){
  237                    cache[x][y] = new Chunk();
  238                    Arrays.fill(cache[x][y].caches, -1);
  239    
  240                    cacheChunk(x, y);
  241                }
  242            }
  243    
  244 >>         Log.info("Time to cache: {0}", Time.elapsed());
  245        }
```
Post-state:
```java
  224    public void clearTiles(){
  225            if(cbatch != null) cbatch.dispose();
  226    
  227            recacheSet.clear();
  228            int chunksx = Mathf.ceil((float)(world.width()) / chunksize),
  229            chunksy = Mathf.ceil((float)(world.height()) / chunksize);
  230            cache = new Chunk[chunksx][chunksy];
  231            cbatch = new MultiCacheBatch(chunksize * chunksize * 5);
  232    
  233            Time.mark();
  234    
  235            for(int x = 0; x < chunksx; x++){
  236                for(int y = 0; y < chunksy; y++){
  237                    cache[x][y] = new Chunk();
  238                    Arrays.fill(cache[x][y].caches, -1);
  239    
  240                    cacheChunk(x, y);
  241                }
  242            }
  243    
  244 >>         Log.debug("Time to cache: {0}", Time.elapsed());
  245        }
```

## OpenKeeper:6d54e8f8c02f:12 — CHANGE_LEVEL

- repo: OpenKeeper  commit: https://github.com/tonihele/OpenKeeper/commit/6d54e8f8c02f69e89a95555610d0652b2f4d4c2b
- method: `LobbyClientService.onInitialize(ClientServiceManager)` in `src/toniarts/openkeeper/game/network/lobby/LobbyClientService.java`
- statement: `logger.log(Level.TRACE, "onInitialize({0})", s)` -> `logger.log(Level.DEBUG, "onInitialize({0})", s)`
- levels: TRACE -> DEBUG

Pre-state:
```java
   85    @Override
   86        protected void onInitialize(ClientServiceManager s) {
   87 >>         logger.log(Level.TRACE, "onInitialize({0})", s);
   88            this.rmiService = getService(RmiClientService.class);
   89            if (rmiService == null) {
   90                throw new RuntimeException("LobbyClientService requires RMI service");
   91            }
   92            logger.log(Level.TRACE, "Sharing session callback.");
   93            rmiService.share(NetworkConstants.LOBBY_CHANNEL, sessionCallback, LobbySessionListener.class);
   94        }
```
Post-state:
```java
   85    @Override
   86        protected void onInitialize(ClientServiceManager s) {
   87 >>         logger.log(Level.DEBUG, "onInitialize({0})", s);
   88            this.rmiService = getService(RmiClientService.class);
   89            if (rmiService == null) {
   90                throw new RuntimeException("LobbyClientService requires RMI service");
   91            }
   92            logger.log(Level.DEBUG, "Sharing session callback.");
   93            rmiService.share(NetworkConstants.LOBBY_CHANNEL, sessionCallback, LobbySessionListener.class);
   94        }
```

## riiablo:ac35310acea2:7 — CHANGE_LEVEL

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/ac35310acea2eda6def3ccd095ae98a215a61e70
- method: `LobbyScreen.show()` in `core/src/com/riiablo/screen/LobbyScreen.java`
- statement: `Gdx.app.log(TAG, t.getMessage(), t)` -> `Gdx.app.error(TAG, t.getMessage(), t)`
- levels: INFO -> ERROR

Pre-state:
```java
      ...
  461                stage.setKeyboardFocus(tfGameName);
  462                Net.HttpRequest request = new HttpRequestBuilder()
  463                    .newRequest()
  464                    .method(Net.HttpMethods.GET)
  465                    .url("http://" + Riiablo.client.getRealm() + ":6112/get-sessions")
  466                    .build();
  467                Gdx.net.sendHttpRequest(request, new Net.HttpResponseListener() {
  468                  @Override
  469                  public void handleHttpResponse(Net.HttpResponse httpResponse) {
  470                    Array<Session> sessions = (Array<Session>) new Json().fromJson(Array.class, httpResponse.getResultAsStream());
  471                    Gdx.app.log(TAG, sessions.toString());
  472                    list.setItems(sessions);
  473                  }
  474    
  475                  @Override
  476                  public void failed(Throwable t) {
  477                    if (t.getClass() == SocketTimeoutException.class
  478                        || t.getClass() == ConnectException.class) {
  479                      Gdx.app.log(TAG, t.getMessage());
  480                    } else {
  481 >>                   Gdx.app.log(TAG, t.getMessage(), t);
  482                    }
  483                  }
  484    
  485                  @Override
  486                  public void cancelled() {
  487                  }
  488                });
  489              }
  490            });
  491          }});
  492        }};
  493        stage.addActor(right);
  494    
  495        final Table left = new Table() {{
  496          setSize(350, 332);
  497          setPosition(55, 115);
  498          add(taChatOutput = new TextArea("", new TextArea.TextFieldStyle() {{
  499            font = Riiablo.fonts.fontformal10;
  500            fontColor = Riiablo.colors.white;
  501            cursor = new TextureRegionDrawable(Riiablo.textures.white);
      ...
```
Post-state:
```java
      ...
  470              public void entered() {
  471                addListener(keyListener);
  472                list.clearItems();
  473                list.getSelection().setRequired(false);
  474                stage.setKeyboardFocus(tfGameName);
  475    
  476                ListGames(new ResponseListener() {
  477                  @Override
  478                  public void handleResponse(MCP packet) {
  479                    Array<GameSession> sessions = new Array<>();
  480                    ListGames listGames = (ListGames) packet.data(new ListGames());
  481                    for (int i = 0, length = listGames.gamesLength(); i < length; i++) {
  482                      sessions.add(new GameSession(listGames.games(i)));
  483                    }
  484                    Gdx.app.log(TAG, sessions.toString());
  485                    list.setItems(sessions);
  486                  }
  487    
  488                  @Override
  489                  public void failed(Throwable t) {
  490 >>                 Gdx.app.error(TAG, t.getMessage(), t);
  491                  }
  492                });
  493              }
  494            });
  495          }});
  496        }};
  497        stage.addActor(right);
  498    
  499        final Table left = new Table() {{
  500          setSize(350, 332);
  501          setPosition(55, 115);
  502          add(taChatOutput = new TextArea("", new TextArea.TextFieldStyle() {{
  503            font = Riiablo.fonts.fontformal10;
  504            fontColor = Riiablo.colors.white;
  505            cursor = new TextureRegionDrawable(Riiablo.textures.white);
  506          }}) {{
  507            setDisabled(true);
  508          }}).grow().row();
  509          add(tfChatInput = new TextField("", textFieldStyle) {{
  510            setTextFieldListener(new TextFieldListener() {
      ...
```

## subspace-infinity:06554893aa03:0 — CHANGE_LEVEL

- repo: subspace-infinity  commit: https://github.com/assofohdz/subspace-infinity/commit/06554893aa03cb14f6d5da47ff35f2ceb54ca757
- method: `GameSessionClientService.move(Quaternion,Vector3f)` in `sim-eth-basic/src/main/java/example/net/client/GameSessionClientService.java`
- statement: `log.info("move(" + dir + ", " + thrust + ")")` -> `log.trace("move(" + dir + ", " + thrust + ")")`
- levels: INFO -> TRACE

Pre-state:
```java
   73    @Override
   74        public void move( Quaternion dir, Vector3f thrust ) {
   75 >>         log.info("move(" + dir + ", " + thrust + ")");
   76            getDelegate().move(dir, thrust);
   77        }
```
Post-state:
```java
   73    @Override
   74        public void move( Quaternion dir, Vector3f thrust ) {
   75            if( log.isTraceEnabled() ) {
   76 >>             log.trace("move(" + dir + ", " + thrust + ")");
   77            }
   78            getDelegate().move(dir, thrust);
   79        }
```

## Mindustry:9f29898713b3:3 — CHANGE_LEVEL

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/9f29898713b3f29d97a7048c1c536eaa40fb2b31
- method: `ContentLoader.logContent()` in `core/src/io/anuke/mindustry/core/ContentLoader.java`
- statement: `Log.info("Total content loaded: {0}", Array.with(ContentType.values()).mapInt(c -> contentMap[c.ordinal()].size).sum())` -> `Log.debug("Total content loaded: {0}", Array.with(ContentType.values()).mapInt(c -> contentMap[c.ordinal()].size).sum())`
- levels: INFO -> DEBUG

Pre-state:
```java
   79    public void logContent(){
   80            //check up ID mapping, make sure it's linear (debug only)
   81            for(Array<Content> arr : contentMap){
   82                for(int i = 0; i < arr.size; i++){
   83                    int id = arr.get(i).id;
   84                    if(id != i){
   85                        throw new IllegalArgumentException("Out-of-order IDs for content '" + arr.get(i) + "' (expected " + i + " but got " + id + ")");
   86                    }
   87                }
   88            }
   89    
   90            Log.info("--- CONTENT INFO ---");
   91            for(int k = 0; k < contentMap.length; k++){
   92                Log.info("[{0}]: loaded {1}", ContentType.values()[k].name(), contentMap[k].size);
   93            }
   94 >>         Log.info("Total content loaded: {0}", Array.with(ContentType.values()).mapInt(c -> contentMap[c.ordinal()].size).sum());
   95            Log.info("-------------------");
   96        }
```
Post-state:
```java
   79    public void logContent(){
   80            //check up ID mapping, make sure it's linear (debug only)
   81            for(Array<Content> arr : contentMap){
   82                for(int i = 0; i < arr.size; i++){
   83                    int id = arr.get(i).id;
   84                    if(id != i){
   85                        throw new IllegalArgumentException("Out-of-order IDs for content '" + arr.get(i) + "' (expected " + i + " but got " + id + ")");
   86                    }
   87                }
   88            }
   89    
   90            Log.debug("--- CONTENT INFO ---");
   91            for(int k = 0; k < contentMap.length; k++){
   92                Log.debug("[{0}]: loaded {1}", ContentType.values()[k].name(), contentMap[k].size);
   93            }
   94 >>         Log.debug("Total content loaded: {0}", Array.with(ContentType.values()).mapInt(c -> contentMap[c.ordinal()].size).sum());
   95            Log.debug("-------------------");
   96        }
```

## subspace-infinity:1c13361d066d:2 — CHANGE_LEVEL

- repo: subspace-infinity  commit: https://github.com/assofohdz/subspace-infinity/commit/1c13361d066d227d970a6617aa51d306ab4bb14a
- method: `ContactSystem.newContact(Contact)` in `infinity/src/main/java/infinity/systems/ContactSystem.java`
- statement: `log.info("Collided: " + bodyTwo.toString() + " with null")` -> `log.debug("Collided: " + bodyTwo + " with null")`
- levels: INFO -> DEBUG

Pre-state:
```java
      ...
   65                    log.info("Disabling contact: "+contact.toString());
   66                    contact.disable();
   67                    return;
   68                }
   69    
   70                final Parent parentOfTwo = ed.getComponent(two, Parent.class);
   71                if (parentOfTwo != null && parentOfTwo.getParentEntity().compareTo(one) == 0) {
   72                    // We have a parent on entity two and its equal to one
   73                    log.info("Disabling contact: "+contact.toString());
   74                    contact.disable();
   75                    return;
   76                }
   77    
   78                log.info("Collision between: " + bodyOne + " and " + bodyTwo);
   79    
   80            } else {
   81                // This happens when a dynamic collides with a static body or the world
   82                if (bodyOne != null) {
   83                    log.info("Collided: " + bodyOne.toString() + " with null");
   84                } else if (bodyTwo != null) {
   85 >>                 log.info("Collided: " + bodyTwo.toString() + " with null");
   86                }
   87    
   88                contact.restitution = 1;
   89            }
   90    
   91        }
```
Post-state:
```java
      ...
   61          final Parent parentOfOne = ed.getComponent(one, Parent.class);
   62    
   63          if (parentOfOne != null && parentOfOne.getParentEntityId().compareTo(two) == 0) {
   64            // We have a parent on entity one and its equal to two
   65            log.debug("Disabling contact because one is a parent of the other: " + contact);
   66            contact.disable();
   67            return;
   68          }
   69    
   70          final Parent parentOfTwo = ed.getComponent(two, Parent.class);
   71          if (parentOfTwo != null && parentOfTwo.getParentEntityId().compareTo(one) == 0) {
   72            // We have a parent on entity two and its equal to one
   73            log.debug("Disabling contact because one is a parent of the other: " + contact);
   74            contact.disable();
   75            return;
   76          }
   77    
   78          log.debug("Collision between: " + bodyOne + " and " + bodyTwo);
   79    
   80        } else{
   81 >>         log.debug("Collided: " + bodyTwo + " with null");
   82            //Restitution should make sure the bounce conserves the energy completely
   83            contact.restitution = 1;
   84          }
   85    
   86        //Now that we have filtered the basics, lets send it to the various systems listening for contacts
   87        for (ContactListener l : listeners) {
   88          l.newContact(contact);
   89        }
   90      }
```

## riiablo:c12747500748:11 — CHANGE_LEVEL

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/c127475007483b9c27634787fbf894500c509938
- method: `StatList.add(int,StatGetter)` in `core/src/com/riiablo/attributes/StatList.java`
- statement: `log.info(indexDebugString(index))` -> `log.debug(indexDebugString(index))`
- levels: INFO -> DEBUG

Pre-state:
```java
  297    public int add(int list, StatGetter src) {
  298        final short stat = src.id();
  299        final int param = src.param();
  300        final int index = indexOf(list, stat, param);
  301        if (log.debugEnabled()) log.debug(
  302            "add(stat: {} ({}), this: {}, src: {})",
  303            stat, entry(stat), index >= 0 ? asString(index) : "null", src.debugString());
  304        if (index >= 0 && ids[index] == stat) {
  305          values[index] += src.value();
  306 >>       if (log.infoEnabled()) log.info(indexDebugString(index));
  307          return index;
  308        } else {
  309          /** TODO: possibility to speed this up with {@link #insertAt} */
  310          final int putIndex = put(list, stat, param, src.value());
  311          assert putIndex == ~index : "index(" + putIndex + ") != expected index(" + ~index + ")";
  312          return putIndex;
  313        }
  314        // max
  315      }
```
Post-state:
```java
  250    public int add(final int list, final StatGetter src) {
  251        if (log.traceEnabled()) log.traceEntry("add(list: {}, src: {})", list, src);
  252        assertMutable();
  253        final short stat = src.id();
  254        final int param = src.param();
  255        final int index = indexOf(list, stat, param);
  256        if (log.traceEnabled()) log.trace(
  257            "add(stat: {} ({}), this: {}, src: {})",
  258            stat, entry(stat), index >= 0 ? asString(index) : "null", src.debugString());
  259        if (index >= 0 && ids[index] == stat) {
  260          values[index] += src.value();
  261 >>       if (log.debugEnabled()) log.debug(indexDebugString(index));
  262          return index;
  263        } else {
  264          /** TODO: possibility to speed this up with {@link #insertAt} */
  265          final int putIndex = put(list, stat, param, src.value());
  266          assert putIndex == ~index : "index(" + putIndex + ") != expected index(" + ~index + ")";
  267          return putIndex;
  268        }
  269        // max
  270      }
```

## Mindustry:76aa409f89b6:3 — CHANGE_LEVEL

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/76aa409f89b6a81166f69571463e26b5d73448cd
- method: `NetServer.onAdminRequest(Player,Player,AdminAction)` in `core/src/io/anuke/mindustry/core/NetServer.java`
- statement: `Log.err("{0} attempted to perform admin action on nonexistant or admin player.", player.name)` -> `Log.warn("{0} attempted to perform admin action on nonexistant or admin player.", player.name)`
- levels: ERROR -> WARN

Pre-state:
```java
  339    @Remote(targets = Loc.client, called = Loc.server)
  340        public static void onAdminRequest(Player player, Player other, AdminAction action){
  341    
  342            if(!player.isAdmin){
  343                Log.err("ACCESS DENIED: Player {0} / {1} attempted to perform admin action without proper security access.",
  344                        player.name, player.con.address);
  345                return;
  346            }
  347    
  348            if(other == null || ((other.isAdmin && !player.isLocal) && other != player)){
  349 >>             Log.err("{0} attempted to perform admin action on nonexistant or admin player.", player.name);
  350                return;
  351            }
  352    
  353            if(action == AdminAction.wave){
  354                //no verification is done, so admins can hypothetically spam waves
  355                //not a real issue, because server owners may want to do just that
  356                state.wavetime = 0f;
  357            }else if(action == AdminAction.ban){
  358                netServer.admins.banPlayerIP(other.con.address);
  359                netServer.kick(other.con.id, KickReason.banned);
  360                Log.info("&lc{0} has banned {1}.", player.name, other.name);
  361            }else if(action == AdminAction.kick){
  362                netServer.kick(other.con.id, KickReason.kick);
  363                Log.info("&lc{0} has kicked {1}.", player.name, other.name);
  364            }else if(action == AdminAction.trace){
  365                //TODO implement
  366                if(player.con != null){
  367                    //Call.onTraceInfo(player.con.id, other.con.trace);
  368                }else{
  369                    //NetClient.onTraceInfo(other.con.trace);
      ...
```
Post-state:
```java
  339    @Remote(targets = Loc.client, called = Loc.server)
  340        public static void onAdminRequest(Player player, Player other, AdminAction action){
  341    
  342            if(!player.isAdmin){
  343                Log.warn("ACCESS DENIED: Player {0} / {1} attempted to perform admin action without proper security access.",
  344                        player.name, player.con.address);
  345                return;
  346            }
  347    
  348            if(other == null || ((other.isAdmin && !player.isLocal) && other != player)){
  349 >>             Log.warn("{0} attempted to perform admin action on nonexistant or admin player.", player.name);
  350                return;
  351            }
  352    
  353            if(action == AdminAction.wave){
  354                //no verification is done, so admins can hypothetically spam waves
  355                //not a real issue, because server owners may want to do just that
  356                state.wavetime = 0f;
  357            }else if(action == AdminAction.ban){
  358                netServer.admins.banPlayerIP(other.con.address);
  359                netServer.kick(other.con.id, KickReason.banned);
  360                Log.info("&lc{0} has banned {1}.", player.name, other.name);
  361            }else if(action == AdminAction.kick){
  362                netServer.kick(other.con.id, KickReason.kick);
  363                Log.info("&lc{0} has kicked {1}.", player.name, other.name);
  364            }else if(action == AdminAction.trace){
  365                //TODO implement
  366                if(player.con != null){
  367                    //Call.onTraceInfo(player.con.id, other.con.trace);
  368                }else{
  369                    //NetClient.onTraceInfo(other.con.trace);
      ...
```

## riiablo:61513798539d:1 — CHANGE_LEVEL

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/61513798539d02528cffafc1ff59be68fd1c5dda
- method: `AssetManager.load0(AssetDesc<T>)` in `core/src/main/java/com/riiablo/asset/AssetManager.java`
- statement: `log.debug("Dependencies: {}", Arrays.toString(dependencies))` -> `log.trace("Dependencies: {}", Arrays.toString(dependencies))`
- levels: DEBUG -> TRACE

Pre-state:
```java
      ...
  190        final AssetContainer container0 = loadedAssets.get(asset);
  191        if (container0 != null) {
  192          return container0.retain();
  193        }
  194    
  195        // create promise
  196        // submit asset loading task
  197        //    get dependencies and submit them
  198        //       add listener to promise to continue
  199        //    after dependencies perform io
  200        //    after io perform async
  201        //    after async submit sync
  202        //    complete promise
  203    
  204        final Promise<T> promise = sync.newPromise();
  205        final AssetContainer[] dependencies = loadDependencies(asset);
  206        final AssetContainer container = AssetContainer.wrap(asset, promise, dependencies);
  207        loadedAssets.put(asset, container);
  208    
  209        // FIXME: below is a workaround since Object[] isn't supported at the moment of writing
  210 >>     if (log.debugEnabled()) log.debug("Dependencies: {}", Arrays.toString(dependencies));
  211        if (dependencies.length > 0) {
  212          deps.execute(new Runnable() {
  213            @Override
  214            public void run() {
  215              PromiseCombiner combiner = new PromiseCombiner(deps);
  216              for (AssetContainer dependency : dependencies) {
  217                combiner.add((Future) dependency.promise);
  218              }
  219    
  220              Promise<Void> combinerPromise = deps.newPromise();
  221              combinerPromise.addListener(new FutureListener<Void>() {
  222                @Override
  223                public void operationComplete(Future<Void> future) {
  224                  ioAsync(container);
  225                }
  226              });
  227              combiner.finish(combinerPromise);
  228            }
  229          });
  230        } else {
      ...
```
Post-state:
```java
      ...
  190        final AssetContainer container0 = loadedAssets.get(asset);
  191        if (container0 != null) {
  192          return container0.retain();
  193        }
  194    
  195        // create promise
  196        // submit asset loading task
  197        //    get dependencies and submit them
  198        //       add listener to promise to continue
  199        //    after dependencies perform io
  200        //    after io perform async
  201        //    after async submit sync
  202        //    complete promise
  203    
  204        final Promise<T> promise = sync.newPromise();
  205        final AssetContainer[] dependencies = loadDependencies(asset);
  206        final AssetContainer container = AssetContainer.wrap(asset, promise, dependencies);
  207        loadedAssets.put(asset, container);
  208    
  209        // FIXME: below is a workaround since Object[] isn't supported at the moment of writing
  210 >>     if (log.traceEnabled()) log.trace("Dependencies: {}", Arrays.toString(dependencies));
  211        if (dependencies.length > 0) {
  212          deps.execute(new Runnable() {
  213            @Override
  214            public void run() {
  215              PromiseCombiner combiner = new PromiseCombiner(deps);
  216              for (AssetContainer dependency : dependencies) {
  217                combiner.add((Future) dependency.promise);
  218              }
  219    
  220              Promise<Void> combinerPromise = deps.newPromise();
  221              combinerPromise.addListener(new FutureListener<Void>() {
  222                @Override
  223                public void operationComplete(Future<Void> future) {
  224                  ioAsync(container);
  225                }
  226              });
  227              combiner.finish(combinerPromise);
  228            }
  229          });
  230        } else {
      ...
```

## riiablo:f60040a5d2ee:9 — CHANGE_LEVEL

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/f60040a5d2eedfce53b0f84619b21f1c67adda8a
- method: `Excel.loadTxt(T,TxtParser)` in `core/src/main/java/com/riiablo/excel/Excel.java`
- statement: `Gdx.app.debug(TAG, String.format("Entry[%d](%s).%s=%s", i, name, field.getName(), Arrays.toString(value)))` -> `log.trace("Entry[{}]({}).{}={}", i, name, field.getName(), Arrays.toString(value))`
- levels: DEBUG -> TRACE

Pre-state:
```java
      ...
  227          for (ObjectMap.Entry<Field, int[]> row : columns.entries()) {
  228            Field field = row.key;
  229            int[] columnIds = row.value;
  230            Class type = field.getType();
  231            assert type.isArray() || columnIds.length == 1 : "field should only correspond to 1 column: " + field.getName() + ", " + columnIds.length + " columns (is it supposed to be an array?)";
  232            if (type == String.class) {
  233              String value = parser.getString(columnIds[0]);
  234              field.set(entry, value);
  235              if (DEBUG_ENTRIES) Gdx.app.debug(TAG, String.format("Entry[%d](%s).%s=%s", i, name, field.getName(), value));
  236            } else if (type == String[].class) {
  237              String[] value = parser.getString(columnIds);
  238              field.set(entry, value);
  239              if (DEBUG_ENTRIES) Gdx.app.debug(TAG, String.format("Entry[%d](%s).%s=%s", i, name, field.getName(), Arrays.toString(value)));
  240            } else if (type == byte.class) {
  241              byte value = parser.getByte(columnIds[0]);
  242              field.setByte(entry, value);
  243              if (DEBUG_ENTRIES) Gdx.app.debug(TAG, String.format("Entry[%d](%s).%s=%s", i, name, field.getName(), value));
  244            } else if (type == byte[].class) {
  245              byte[] value = parser.getByte(columnIds);
  246              field.set(entry, value);
  247 >>           if (DEBUG_ENTRIES) Gdx.app.debug(TAG, String.format("Entry[%d](%s).%s=%s", i, name, field.getName(), Arrays.toString(value)));
  248            } else if (type == short.class) {
  249              short value = parser.getShort(columnIds[0]);
  250              field.setShort(entry, value);
  251              if (DEBUG_ENTRIES) Gdx.app.debug(TAG, String.format("Entry[%d](%s).%s=%s", i, name, field.getName(), value));
  252            } else if (type == short[].class) {
  253              short[] value = parser.getShort(columnIds);
  254              field.set(entry, value);
  255              if (DEBUG_ENTRIES) Gdx.app.debug(TAG, String.format("Entry[%d](%s).%s=%s", i, name, field.getName(), Arrays.toString(value)));
  256            } else if (type == int.class) {
  257              int value = parser.getInt(columnIds[0]);
  258              field.setInt(entry, value);
  259              if (DEBUG_ENTRIES) Gdx.app.debug(TAG, String.format("Entry[%d](%s).%s=%s", i, name, field.getName(), value));
  260            } else if (type == int[].class) {
  261              int[] value = parser.getInt(columnIds);
  262              field.set(entry, value);
  263              if (DEBUG_ENTRIES) Gdx.app.debug(TAG, String.format("Entry[%d](%s).%s=%s", i, name, field.getName(), Arrays.toString(value)));
  264            } else if (type == long.class) {
  265              long value = parser.getLong(columnIds[0]);
  266              field.setLong(entry, value);
  267              if (DEBUG_ENTRIES) Gdx.app.debug(TAG, String.format("Entry[%d](%s).%s=%s", i, name, field.getName(), value));
      ...
```
Post-state:
```java
      ...
  233          for (ObjectMap.Entry<Field, int[]> row : columns.entries()) {
  234            Field field = row.key;
  235            int[] columnIds = row.value;
  236            Class type = field.getType();
  237            assert type.isArray() || columnIds.length == 1 : "field should only correspond to 1 column: " + field.getName() + ", " + columnIds.length + " columns (is it supposed to be an array?)";
  238            if (type == String.class) {
  239              String value = parser.getString(columnIds[0]);
  240              field.set(entry, value);
  241              if (DEBUG_ENTRIES) log.trace("Entry[{}]({}).{}={}", i, name, field.getName(), value);
  242            } else if (type == String[].class) {
  243              String[] value = parser.getString(columnIds);
  244              field.set(entry, value);
  245              if (DEBUG_ENTRIES) log.trace("Entry[{}]({}).{}={}", i, name, field.getName(), Arrays.toString(value));
  246            } else if (type == byte.class) {
  247              byte value = parser.getByte(columnIds[0]);
  248              field.setByte(entry, value);
  249              if (DEBUG_ENTRIES) log.trace("Entry[{}]({}).{}={}", i, name, field.getName(), value);
  250            } else if (type == byte[].class) {
  251              byte[] value = parser.getByte(columnIds);
  252              field.set(entry, value);
  253 >>           if (DEBUG_ENTRIES) log.trace("Entry[{}]({}).{}={}", i, name, field.getName(), Arrays.toString(value));
  254            } else if (type == short.class) {
  255              short value = parser.getShort(columnIds[0]);
  256              field.setShort(entry, value);
  257              if (DEBUG_ENTRIES) log.trace("Entry[{}]({}).{}={}", i, name, field.getName(), value);
  258            } else if (type == short[].class) {
  259              short[] value = parser.getShort(columnIds);
  260              field.set(entry, value);
  261              if (DEBUG_ENTRIES) log.trace("Entry[{}]({}).{}={}", i, name, field.getName(), Arrays.toString(value));
  262            } else if (type == int.class) {
  263              int value = parser.getInt(columnIds[0]);
  264              field.setInt(entry, value);
  265              if (DEBUG_ENTRIES) log.trace("Entry[{}]({}).{}={}", i, name, field.getName(), value);
  266            } else if (type == int[].class) {
  267              int[] value = parser.getInt(columnIds);
  268              field.set(entry, value);
  269              if (DEBUG_ENTRIES) log.trace("Entry[{}]({}).{}={}", i, name, field.getName(), Arrays.toString(value));
  270            } else if (type == long.class) {
  271              long value = parser.getLong(columnIds[0]);
  272              field.setLong(entry, value);
  273              if (DEBUG_ENTRIES) log.trace("Entry[{}]({}).{}={}", i, name, field.getName(), value);
      ...
```

## subspace-infinity:143065ecc267:4 — CHANGE_LEVEL

- repo: subspace-infinity  commit: https://github.com/assofohdz/subspace-infinity/commit/143065ecc26781a4b191838df9a18a059f81af3d
- method: `GameSessionHostedService.startHostingOnConnection(HostedConnection,EntityId)` in `subspace-infinity/src/main/java/infinity/net/server/GameSessionHostedService.java`
- statement: `log.debug("startHostingOnConnection(" + conn + ")")` -> `log.info("startHostingOnConnection(" + conn + ")")`
- levels: DEBUG -> INFO

Pre-state:
```java
  150    public void startHostingOnConnection(HostedConnection conn, EntityId player) {
  151    
  152 >>         log.debug("startHostingOnConnection(" + conn + ")");
  153    
  154            GameSessionImpl session = new GameSessionImpl(player, conn);
  155            
  156            entitySessionMap.put(player, session);
  157            
  158            conn.setAttribute(ATTRIBUTE_SESSION, session);
  159    
  160            // Expose the session as an RMI resource to the client
  161            RmiRegistry rmi = rmiService.getRmiRegistry(conn);
  162            rmi.share(session, GameSession.class);
  163    
  164            players.add(session);
  165    
  166            session.initialize();
  167    
  168            // Setup to start using SimEthereal synching
  169            getService(EtherealHost.class).startHostingOnConnection(conn);
  170            getService(EtherealHost.class).setConnectionObject(conn, session.shipEntity.getId(), new Vec3d());
  171    
  172            // Start hosting on the chat server also
      ...
```
Post-state:
```java
  150    public void startHostingOnConnection(HostedConnection conn, EntityId player) {
  151    
  152 >>         log.info("startHostingOnConnection(" + conn + ")");
  153    
  154            GameSessionImpl session = new GameSessionImpl(player, conn);
  155            
  156            entitySessionMap.put(player, session);
  157            
  158            conn.setAttribute(ATTRIBUTE_SESSION, session);
  159    
  160            // Expose the session as an RMI resource to the client
  161            RmiRegistry rmi = rmiService.getRmiRegistry(conn);
  162            rmi.share(session, GameSession.class);
  163    
  164            players.add(session);
  165    
  166            session.initialize();
  167    
  168            // Setup to start using SimEthereal synching
  169            getService(EtherealHost.class).startHostingOnConnection(conn);
  170            getService(EtherealHost.class).setConnectionObject(conn, session.shipEntity.getId(), new Vec3d());
  171    
  172            // Start hosting on the chat server also
      ...
```

## subspace-infinity:1cb77ff9cb02:3 — CHANGE_LEVEL

- repo: subspace-infinity  commit: https://github.com/assofohdz/subspace-infinity/commit/1cb77ff9cb02c6ec8c42a68ee34767156ce08803
- method: `ModelViewState.updateModel(Spatial,Entity,boolean)` in `subspace-infinity/src/main/java/infinity/client/view/ModelViewState.java`
- statement: `log.info("Position ("+spatial.getName()+"): "+spatial.getLocalTranslation()+", "+pos.getFacing())` -> `log.debug("Position (" + spatial.getName() + "): " + spatial.getLocalTranslation() + ", " + pos.getFacing())`
- levels: INFO -> DEBUG

Pre-state:
```java
  494    protected void updateModel(Spatial spatial, Entity entity, boolean updatePosition) {
  495            if (updatePosition) {
  496                Position pos = entity.get(Position.class);
  497    
  498                // I like to move it... move it...
  499                spatial.setLocalTranslation(pos.getLocation().toVector3f());
  500                spatial.setLocalRotation(pos.getFacing().toQuaternion());
  501    
  502 >>             log.info("Position ("+spatial.getName()+"): "+spatial.getLocalTranslation()+", "+pos.getFacing());
  503            }
  504        }
```
Post-state:
```java
  496    protected void updateModel(Spatial spatial, Entity entity, boolean updatePosition) {
  497            if (updatePosition) {
  498                Position pos = entity.get(Position.class);
  499    
  500                // I like to move it... move it...
  501                spatial.setLocalTranslation(pos.getLocation().toVector3f());
  502                spatial.setLocalRotation(pos.getFacing().toQuaternion());
  503    
  504 >>             log.debug("Position (" + spatial.getName() + "): " + spatial.getLocalTranslation() + ", " + pos.getFacing());
  505            }
  506        }
```

## Mindustry:e23119e33033:0 — CHANGE_LEVEL

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/e23119e3303314b279a4961aa371dc9d7971fa6a
- method: `EntityProcess.process(RoundEnvironment)` in `annotations/src/main/java/mindustry/annotations/impl/EntityProcess.java`
- statement: `Log.info("&gGenerating interface for " + component.name())` -> `Log.debug("&gGenerating interface for " + component.name())`
- levels: INFO -> DEBUG

Pre-state:
```java
      ...
  125                        if(!signatures.contains(cname + "()")){
  126                            inter.addMethod(MethodSpec.methodBuilder(cname).addModifiers(Modifier.ABSTRACT, Modifier.PUBLIC)
  127                            .addAnnotations(Array.with(field.annotations()).select(a -> a.toString().contains("Null")).map(AnnotationSpec::get))
  128                            .returns(field.tname()).build());
  129                        }
  130    
  131                        //setter
  132                        if(!field.is(Modifier.FINAL) && !signatures.contains(cname + "(" + field.mirror().toString() + ")") &&
  133                        !field.annotations().contains(f -> f.toString().equals("@mindustry.annotations.Annotations.ReadOnly"))){
  134                            inter.addMethod(MethodSpec.methodBuilder(cname).addModifiers(Modifier.ABSTRACT, Modifier.PUBLIC)
  135                            .addParameter(ParameterSpec.builder(field.tname(), field.name())
  136                            .addAnnotations(Array.with(field.annotations())
  137                            .select(a -> a.toString().contains("Null")).map(AnnotationSpec::get)).build()).build());
  138                        }
  139                    }
  140    
  141                    write(inter);
  142    
  143                    //LOGGING
  144    
  145 >>                 Log.info("&gGenerating interface for " + component.name());
  146    
  147                    for(TypeName tn : inter.superinterfaces){
  148                        Log.info("&g> &lbextends {0}", simpleName(tn.toString()));
  149                    }
  150    
  151                    //log methods generated
  152                    for(MethodSpec spec : inter.methodSpecs){
  153                        Log.info("&g> > &c{0} {1}({2})", simpleName(spec.returnType.toString()), spec.name, Array.with(spec.parameters).toString(", ", p -> simpleName(p.type.toString()) + " " + p.name));
  154                    }
  155    
  156                    Log.info("");
  157                }
  158    
  159                //generate special render layer interfaces
  160                for(DrawLayer layer : DrawLayer.values()){
  161                    //create the DrawLayer interface that entities need to implement
  162                    String name = "DrawLayer" + Strings.capitalize(layer.name()) + "c";
  163                    TypeSpec.Builder inter = TypeSpec.interfaceBuilder(name)
  164                    .addSuperinterface(tname(packageName + ".Entityc"))
  165                    .addModifiers(Modifier.PUBLIC).addAnnotation(EntityInterface.class);
      ...
```
Post-state:
```java
      ...
  125                        if(!signatures.contains(cname + "()")){
  126                            inter.addMethod(MethodSpec.methodBuilder(cname).addModifiers(Modifier.ABSTRACT, Modifier.PUBLIC)
  127                            .addAnnotations(Array.with(field.annotations()).select(a -> a.toString().contains("Null")).map(AnnotationSpec::get))
  128                            .returns(field.tname()).build());
  129                        }
  130    
  131                        //setter
  132                        if(!field.is(Modifier.FINAL) && !signatures.contains(cname + "(" + field.mirror().toString() + ")") &&
  133                        !field.annotations().contains(f -> f.toString().equals("@mindustry.annotations.Annotations.ReadOnly"))){
  134                            inter.addMethod(MethodSpec.methodBuilder(cname).addModifiers(Modifier.ABSTRACT, Modifier.PUBLIC)
  135                            .addParameter(ParameterSpec.builder(field.tname(), field.name())
  136                            .addAnnotations(Array.with(field.annotations())
  137                            .select(a -> a.toString().contains("Null")).map(AnnotationSpec::get)).build()).build());
  138                        }
  139                    }
  140    
  141                    write(inter);
  142    
  143                    //LOGGING
  144    
  145 >>                 Log.debug("&gGenerating interface for " + component.name());
  146    
  147                    for(TypeName tn : inter.superinterfaces){
  148                        Log.debug("&g> &lbextends {0}", simpleName(tn.toString()));
  149                    }
  150    
  151                    //log methods generated
  152                    for(MethodSpec spec : inter.methodSpecs){
  153                        Log.debug("&g> > &c{0} {1}({2})", simpleName(spec.returnType.toString()), spec.name, Array.with(spec.parameters).toString(", ", p -> simpleName(p.type.toString()) + " " + p.name));
  154                    }
  155    
  156                    Log.debug("");
  157                }
  158    
  159                //generate special render layer interfaces
  160                for(DrawLayer layer : DrawLayer.values()){
  161                    //create the DrawLayer interface that entities need to implement
  162                    String name = "DrawLayer" + Strings.capitalize(layer.name()) + "c";
  163                    TypeSpec.Builder inter = TypeSpec.interfaceBuilder(name)
  164                    .addSuperinterface(tname(packageName + ".Entityc"))
  165                    .addModifiers(Modifier.PUBLIC).addAnnotation(EntityInterface.class);
      ...
```

## Mindustry:9f29898713b3:7 — CHANGE_LEVEL

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/9f29898713b3f29d97a7048c1c536eaa40fb2b31
- method: `Mods.loadAsync()` in `core/src/io/anuke/mindustry/mod/Mods.java`
- statement: `Log.info("Time to pack textures: {0}", Time.elapsed())` -> `Log.debug("Time to pack textures: {0}", Time.elapsed())`
- levels: INFO -> DEBUG

Pre-state:
```java
      ...
   95            Time.mark();
   96    
   97            packer = new MultiPacker();
   98    
   99            for(LoadedMod mod : loaded){
  100                Array<FileHandle> sprites = mod.root.child("sprites").findAll(f -> f.extension().equals("png"));
  101                Array<FileHandle> overrides = mod.root.child("sprites-override").findAll(f -> f.extension().equals("png"));
  102                packSprites(sprites, mod, true);
  103                packSprites(overrides, mod, false);
  104                Log.info("Packed {0} images for mod '{1}'.", sprites.size + overrides.size, mod.meta.name);
  105                totalSprites += sprites.size + overrides.size;
  106            }
  107    
  108            for(AtlasRegion region : Core.atlas.getRegions()){
  109                PageType type = getPage(region);
  110                if(!packer.has(type, region.name)){
  111                    packer.add(type, region.name, Core.atlas.getPixmap(region));
  112                }
  113            }
  114    
  115 >>         Log.info("Time to pack textures: {0}", Time.elapsed());
  116        }
```
Post-state:
```java
      ...
   95            Time.mark();
   96    
   97            packer = new MultiPacker();
   98    
   99            for(LoadedMod mod : loaded){
  100                Array<FileHandle> sprites = mod.root.child("sprites").findAll(f -> f.extension().equals("png"));
  101                Array<FileHandle> overrides = mod.root.child("sprites-override").findAll(f -> f.extension().equals("png"));
  102                packSprites(sprites, mod, true);
  103                packSprites(overrides, mod, false);
  104                Log.debug("Packed {0} images for mod '{1}'.", sprites.size + overrides.size, mod.meta.name);
  105                totalSprites += sprites.size + overrides.size;
  106            }
  107    
  108            for(AtlasRegion region : Core.atlas.getRegions()){
  109                PageType type = getPage(region);
  110                if(!packer.has(type, region.name)){
  111                    packer.add(type, region.name, Core.atlas.getPixmap(region));
  112                }
  113            }
  114    
  115 >>         Log.debug("Time to pack textures: {0}", Time.elapsed());
  116        }
```

## Mindustry:49f68be2cb81:0 — CHANGE_LEVEL

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/49f68be2cb8114c1f939b5d55fd0fa01fce28a03
- method: `Mods.load()` in `core/src/mindustry/mod/Mods.java`
- statement: `Log.info("Plugin '@' is outdated and needs to be ported to 6.0! Update its main class to inherit from 'mindustry.mod.Plugin'. See https://mindustrygame.github.io/wiki/modding/6-migrationv6/", file.nam` -> `Log.warn("Plugin '@' is outdated and needs to be ported to v7! Update its main class to inherit from 'mindustry.mod.Plugin'.", file.name())`
- levels: INFO -> WARN

Pre-state:
```java
      ...
  490                metas.add(meta);
  491                mapping.put(meta.internalName, file);
  492            }
  493    
  494            var resolved = resolveDependencies(metas);
  495            for(var entry : resolved){
  496                var file = mapping.get(entry.key);
  497                var steam = platform.getWorkshopContent(LoadedMod.class).contains(file);
  498    
  499                Log.debug("[Mods] Loading mod @", file);
  500    
  501                try{
  502                    LoadedMod mod = loadMod(file, false, entry.value == ModState.enabled);
  503                    mod.state = entry.value;
  504                    mods.add(mod);
  505                    //invalidate ordered mods cache
  506                    lastOrderedMods = null;
  507                    if(steam) mod.addSteamID(file.name());
  508                }catch(Throwable e){
  509                    if(e instanceof ClassNotFoundException && e.getMessage().contains("mindustry.plugin.Plugin")){
  510 >>                     Log.info("Plugin '@' is outdated and needs to be ported to 6.0! Update its main class to inherit from 'mindustry.mod.Plugin'. See https://mindustrygame.github.io/wiki/modding/6-migrationv6/", file.name());
  511                    }else if(steam){
  512                        Log.err("Failed to load mod workshop file @. Skipping.", file);
  513                        Log.err(e);
  514                    }else{
  515                        Log.err("Failed to load mod file @. Skipping.", file);
  516                        Log.err(e);
  517                    }
  518                }
  519            }
  520    
  521            // Resolve the state
  522            mods.each(this::updateDependencies);
  523            for(var mod : mods){
  524                // Skip mods where the state has already been resolved
  525                if(mod.state != ModState.enabled) continue;
  526                if(!mod.isSupported()){
  527                    mod.state = ModState.unsupported;
  528                }else if(!mod.shouldBeEnabled()){
  529                    mod.state = ModState.disabled;
  530                }
      ...
```
Post-state:
```java
      ...
  484                metas.add(meta);
  485                mapping.put(meta.internalName, file);
  486            }
  487    
  488            var resolved = resolveDependencies(metas);
  489            for(var entry : resolved){
  490                var file = mapping.get(entry.key);
  491                var steam = platform.getWorkshopContent(LoadedMod.class).contains(file);
  492    
  493                Log.debug("[Mods] Loading mod @", file);
  494    
  495                try{
  496                    LoadedMod mod = loadMod(file, false, entry.value == ModState.enabled);
  497                    mod.state = entry.value;
  498                    mods.add(mod);
  499                    //invalidate ordered mods cache
  500                    lastOrderedMods = null;
  501                    if(steam) mod.addSteamID(file.name());
  502                }catch(Throwable e){
  503                    if(e instanceof ClassNotFoundException && e.getMessage().contains("mindustry.plugin.Plugin")){
  504 >>                     Log.warn("Plugin '@' is outdated and needs to be ported to v7! Update its main class to inherit from 'mindustry.mod.Plugin'.", file.name());
  505                    }else if(steam){
  506                        Log.err("Failed to load mod workshop file @. Skipping.", file);
  507                        Log.err(e);
  508                    }else{
  509                        Log.err("Failed to load mod file @. Skipping.", file);
  510                        Log.err(e);
  511                    }
  512                }
  513            }
  514    
  515            // Resolve the state
  516            mods.each(this::updateDependencies);
  517            for(var mod : mods){
  518                // Skip mods where the state has already been resolved
  519                if(mod.state != ModState.enabled) continue;
  520                if(!mod.isSupported()){
  521                    mod.state = ModState.unsupported;
  522                }else if(!mod.shouldBeEnabled()){
  523                    mod.state = ModState.disabled;
  524                }
      ...
```

## riiablo:b8a5049adbf8:2 — CHANGE_LEVEL

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/b8a5049adbf8f1b9136f58ebd7619a3f3b42bb34
- method: `ClientNetworkReceiver.Synchronize(D2GS)` in `core/src/com/riiablo/engine/client/ClientNetworkReceiver.java`
- statement: `Gdx.app.log(TAG, "syncing " + entityId)` -> `Gdx.app.debug(TAG, "syncing " + entityId)`
- levels: INFO -> DEBUG

Pre-state:
```java
  255    private void Synchronize(D2GS packet) {
  256        Sync sync = (Sync) packet.data(new Sync());
  257        int entityId = syncIds.get(sync.entityId());
  258        if (entityId == Engine.INVALID_ENTITY) {
  259          syncIds.put(sync.entityId(), entityId = createEntity(sync));
  260        }
  261    
  262        int flags1 = Dirty.NONE;
  263        int flags2 = Dirty.NONE;
  264 >>     Gdx.app.log(TAG, "syncing " + entityId);
  265        for (int i = 0, len = sync.dataTypeLength(); i < len; i++) {
  266          switch (sync.dataType(i)) {
  267            case SyncData.ClassP:
  268            case SyncData.PlayerP:
  269            case SyncData.DS1ObjectWrapperP:
  270              break;
  271            case SyncData.CofComponentsP: {
  272              CofComponentsP data = (CofComponentsP) sync.data(new CofComponentsP(), i);
  273              for (int j = 0, s0 = data.componentLength(); j < s0; j++) {
  274                cofs.setComponent(entityId, j, data.component(j));
  275              }
  276              break;
  277            }
  278            case SyncData.CofTransformsP: {
  279              CofTransformsP data = (CofTransformsP) sync.data(new CofTransformsP(), i);
  280              for (int j = 0, s0 = data.transformLength(); j < s0; j++) {
  281                flags1 |= cofs.setTransform(entityId, j, (byte) data.transform(j));
  282              }
  283              break;
  284            }
      ...
```
Post-state:
```java
  271    private void Synchronize(D2GS packet) {
  272        Sync sync = (Sync) packet.data(new Sync());
  273        int entityId = syncIds.get(sync.entityId());
  274        if (entityId == Engine.INVALID_ENTITY) {
  275          syncIds.put(sync.entityId(), entityId = createEntity(sync));
  276        }
  277    
  278        int tFlags = Dirty.NONE;
  279        int aFlags = Dirty.NONE;
  280 >>     if (DEBUG_SYNC) Gdx.app.debug(TAG, "syncing " + entityId);
  281        for (int i = 0, len = sync.dataTypeLength(); i < len; i++) {
  282          switch (sync.dataType(i)) {
  283            case SyncData.ClassP:
  284            case SyncData.PlayerP:
  285            case SyncData.DS1ObjectWrapperP:
  286              break;
  287            case SyncData.CofComponentsP: {
  288              CofComponentsP data = (CofComponentsP) sync.data(new CofComponentsP(), i);
  289              for (int j = 0, s0 = data.componentLength(); j < s0; j++) {
  290                cofs.setComponent(entityId, j, data.component(j));
  291              }
  292              break;
  293            }
  294            case SyncData.CofTransformsP: {
  295              CofTransformsP data = (CofTransformsP) sync.data(new CofTransformsP(), i);
  296              for (int j = 0, s0 = data.transformLength(); j < s0; j++) {
  297                tFlags |= cofs.setTransform(entityId, j, (byte) data.transform(j));
  298              }
  299              break;
  300            }
      ...
```

## OpenKeeper:8a05c84a6412:0 — CHANGE_LEVEL

- repo: OpenKeeper  commit: https://github.com/tonihele/OpenKeeper/commit/8a05c84a64122a8bea6c39417c69e24362a748f1
- method: `CreaturesController.spawnHeroParty(short,PartyType,Vector2f)` in `src/toniarts/openkeeper/game/controller/CreaturesController.java`
- statement: `logger.log(Level.TRACE, "Re-spawning party {0}!", partyId)` -> `logger.log(Level.DEBUG, "Re-spawning party {0}!", partyId)`
- levels: TRACE -> DEBUG

Pre-state:
```java
  485    @Override
  486        public void spawnHeroParty(short partyId, PartyType partyType, Vector2f position) {
  487            /**
  488             * In the game manual it is said that it is entirely possible to have
  489             * multiple parties with the same party ID, the old party just isn't
  490             * controlled anymore
  491             */
  492            IPartyController partyController = creaturePartiesByPartyId.get(partyId);
  493            if (partyController.isCreated()) {
  494                partyController = new PartyController(heroParties.get(partyId));
  495 >>             logger.log(Level.TRACE, "Re-spawning party {0}!", partyId);
  496            }
  497            partyController.setType(partyType);
  498            partyController.create();
  499            for (Thing.GoodCreature creature : partyController.getMembers()) {
  500                EntityId entityId = spawnCreature(creature, position);
  501                entityData.setComponent(entityId, new Party(partyController.getId()));
  502    
  503                partyController.addMemberInstance(creature, createController(entityId));
  504            }
  505            creaturePartiesByPartyId.put(partyId, partyController);
  506    
  507            // TODO: Hmm, should we clean these up...
  508            creaturePartiesById.put(partyController.getId(), partyController);
  509    
  510            // TODO: listener, mainly for the PartyTrigger, to replace the party with new instance just in case
  511        }
```
Post-state:
```java
  485    @Override
  486        public void spawnHeroParty(short partyId, PartyType partyType, Vector2f position) {
  487            /**
  488             * In the game manual it is said that it is entirely possible to have
  489             * multiple parties with the same party ID, the old party just isn't
  490             * controlled anymore
  491             */
  492            IPartyController partyController = creaturePartiesByPartyId.get(partyId);
  493            if (partyController.isCreated()) {
  494                partyController = new PartyController(heroParties.get(partyId));
  495 >>             logger.log(Level.DEBUG, "Re-spawning party {0}!", partyId);
  496            }
  497            partyController.setType(partyType);
  498            partyController.create();
  499            for (Thing.GoodCreature creature : partyController.getMembers()) {
  500                EntityId entityId = spawnCreature(creature, position);
  501                entityData.setComponent(entityId, new Party(partyController.getId()));
  502    
  503                partyController.addMemberInstance(creature, createController(entityId));
  504            }
  505            creaturePartiesByPartyId.put(partyId, partyController);
  506    
  507            // TODO: Hmm, should we clean these up...
  508            creaturePartiesById.put(partyController.getId(), partyController);
  509    
  510            // TODO: listener, mainly for the PartyTrigger, to replace the party with new instance just in case
  511        }
```

## subspace-infinity:71214a895762:1 — CHANGE_LEVEL

- repo: subspace-infinity  commit: https://github.com/assofohdz/subspace-infinity/commit/71214a895762e28c4f4ee8b81d184eec9352d67d
- method: `ConnectState.ConnectionObserver.clientDisconnected(Client,DisconnectInfo)` in `sim-eth-basic/src/main/java/example/ConnectState.java`
- statement: `log.trace("clientDisconnected(" + c + ", " + info + ")")` -> `log.info("clientDisconnected(" + c + ", " + info + ")")`
- levels: TRACE -> INFO

Pre-state:
```java
  217    public void clientDisconnected( final Client c, final DisconnectInfo info ) {
  218 >>             log.trace("clientDisconnected(" + c + ", " + info + ")");        
  219                getApplication().enqueue(new Callable() {
  220                        public Object call() {
  221                            disconnected(info);
  222                            return null;
  223                        }
  224                    });
  225            }
```
Post-state:
```java
  217    public void clientDisconnected( final Client c, final DisconnectInfo info ) {
  218 >>             log.info("clientDisconnected(" + c + ", " + info + ")");        
  219                getApplication().enqueue(new Callable() {
  220                        public Object call() {
  221                            disconnected(info);
  222                            return null;
  223                        }
  224                    });
  225            }
```

## Mindustry:9f4d44f0f337:0 — CHANGE_LEVEL

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/9f4d44f0f337db0f6a222fdcc00226037847bac7
- method: `Mods.loadScripts()` in `core/src/io/anuke/mindustry/mod/Mods.java`
- statement: `Log.info("[{0}] Found {1} scripts.", mod.meta.name, mod.scripts.size)` -> `Log.debug("[{0}] Found {1} scripts.", mod.meta.name, mod.scripts.size)`
- levels: INFO -> DEBUG

Pre-state:
```java
  387    public void loadScripts(){
  388            Time.mark();
  389    
  390            try{
  391                for(LoadedMod mod : loaded){
  392                    if(mod.root.child("scripts").exists()){
  393                        content.setCurrentMod(mod);
  394                        mod.scripts = mod.root.child("scripts").findAll(f -> f.extension().equals("js"));
  395 >>                     Log.info("[{0}] Found {1} scripts.", mod.meta.name, mod.scripts.size);
  396    
  397                        for(FileHandle file : mod.scripts){
  398                            try{
  399                                if(scripts == null){
  400                                    scripts = platform.createScripts();
  401                                }
  402                                scripts.run(mod, file);
  403                            }catch(Throwable e){
  404                                Core.app.post(() -> {
  405                                    Log.err("Error loading script {0} for mod {1}.", file.name(), mod.meta.name);
  406                                    e.printStackTrace();
  407                                    //if(!headless) ui.showException(e);
  408                                });
  409                                break;
  410                            }
  411                        }
  412                    }
  413                }
  414            }finally{
  415                content.setCurrentMod(null);
      ...
```
Post-state:
```java
  387    public void loadScripts(){
  388            Time.mark();
  389    
  390            try{
  391                for(LoadedMod mod : loaded){
  392                    if(mod.root.child("scripts").exists()){
  393                        content.setCurrentMod(mod);
  394                        mod.scripts = mod.root.child("scripts").findAll(f -> f.extension().equals("js"));
  395 >>                     Log.debug("[{0}] Found {1} scripts.", mod.meta.name, mod.scripts.size);
  396    
  397                        for(FileHandle file : mod.scripts){
  398                            try{
  399                                if(scripts == null){
  400                                    scripts = platform.createScripts();
  401                                }
  402                                scripts.run(mod, file);
  403                            }catch(Throwable e){
  404                                Core.app.post(() -> {
  405                                    Log.err("Error loading script {0} for mod {1}.", file.name(), mod.meta.name);
  406                                    e.printStackTrace();
  407                                    //if(!headless) ui.showException(e);
  408                                });
  409                                break;
  410                            }
  411                        }
  412                    }
  413                }
  414            }finally{
  415                content.setCurrentMod(null);
      ...
```

## Mindustry:955dc5f48d89:2 — CHANGE_LEVEL

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/955dc5f48d899707fc6c5d66c26034bb63840d8a
- method: `Mods.loadContent()` in `core/src/io/anuke/mindustry/mod/Mods.java`
- statement: `Log.info("[{0}] Loaded '{1}'.", mod.meta.name,
                                        (loaded instanceof UnlockableContent ? ((UnlockableContent)loaded).localizedName : loaded))` -> `Log.debug("[{0}] Loaded '{1}'.", mod.meta.name,
                                        (loaded instanceof UnlockableContent ? ((UnlockableContent)loaded).localizedName : loaded))`
- levels: INFO -> DEBUG

Pre-state:
```java
  276    public void loadContent(){
  277            for(LoadedMod mod : loaded){
  278                safeRun(mod, () -> {
  279                    if(mod.root.child("content").exists()){
  280                        FileHandle contentRoot = mod.root.child("content");
  281                        for(ContentType type : ContentType.all){
  282                            FileHandle folder = contentRoot.child(type.name().toLowerCase() + "s");
  283                            if(folder.exists()){
  284                                for(FileHandle file : folder.list()){
  285                                    if(file.extension().equals("json")){
  286                                        try{
  287                                            //this binds the content but does not load it entirely
  288                                            Content loaded = parser.parse(mod, file.nameWithoutExtension(), file.readString("UTF-8"), file, type);
  289 >>                                         Log.info("[{0}] Loaded '{1}'.", mod.meta.name,
  290                                            (loaded instanceof UnlockableContent ? ((UnlockableContent)loaded).localizedName : loaded));
  291                                        }catch(Exception e){
  292                                            throw new RuntimeException("Failed to parse content file '" + file + "' for mod '" + mod.meta.name + "'.", e);
  293                                        }
  294                                    }
  295                                }
  296                            }
  297                        }
  298                    }
  299                });
  300            }
  301    
  302            //this finishes parsing content fields
  303            parser.finishParsing();
  304    
  305            //load content for code mods
  306            each(Mod::loadContent);
  307        }
```
Post-state:
```java
  278    public void loadContent(){
  279            for(LoadedMod mod : loaded){
  280                safeRun(mod, () -> {
  281                    if(mod.root.child("content").exists()){
  282                        FileHandle contentRoot = mod.root.child("content");
  283                        for(ContentType type : ContentType.all){
  284                            FileHandle folder = contentRoot.child(type.name().toLowerCase() + "s");
  285                            if(folder.exists()){
  286                                for(FileHandle file : folder.list()){
  287                                    if(file.extension().equals("json")){
  288                                        try{
  289                                            //this binds the content but does not load it entirely
  290                                            Content loaded = parser.parse(mod, file.nameWithoutExtension(), file.readString("UTF-8"), file, type);
  291 >>                                         Log.debug("[{0}] Loaded '{1}'.", mod.meta.name,
  292                                            (loaded instanceof UnlockableContent ? ((UnlockableContent)loaded).localizedName : loaded));
  293                                        }catch(Exception e){
  294                                            throw new RuntimeException("Failed to parse content file '" + file + "' for mod '" + mod.meta.name + "'.", e);
  295                                        }
  296                                    }
  297                                }
  298                            }
  299                        }
  300                    }
  301                });
  302            }
  303    
  304            //this finishes parsing content fields
  305            parser.finishParsing();
  306    
  307            //load content for code mods
  308            each(Mod::loadContent);
  309        }
```

## Mindustry:2165a2af7d7d:0 — CHANGE_LEVEL

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/2165a2af7d7d179daa9c737e03d01de1929bb793
- method: `SectorDataGenerator.main(String[])` in `tools/src/mindustry/tools/SectorDataGenerator.java`
- statement: `Log.info("Sector {0} has {1}/{2} water -> naval", sector.id, waterFloors, totalFloors)` -> `Log.debug("Sector {0} has {1}/{2} water -> naval", sector.id, waterFloors, totalFloors)`
- levels: INFO -> DEBUG

Pre-state:
```java
      ...
   78                        }
   79                    }
   80    
   81                    CoreEntity entity = Team.sharded.core();
   82                    int cx = entity.tileX(), cy = entity.tileY();
   83    
   84                    int nearTiles = 0;
   85                    int waterCheckRad = 5;
   86    
   87                    //check for water presence
   88                    for(int rx = -waterCheckRad; rx <= waterCheckRad; rx++){
   89                        for(int ry = -waterCheckRad; ry <= waterCheckRad; ry++){
   90                            Tile tile = world.tile(cx + rx, cy + ry);
   91                            if(tile == null || tile.floor().liquidDrop != null){
   92                                nearTiles ++;
   93                            }
   94                        }
   95                    }
   96    
   97                    if(waterFloors / totalFloors >= 0.6f){
   98 >>                     Log.info("Sector {0} has {1}/{2} water -> naval", sector.id, waterFloors, totalFloors);
   99                    }
  100    
  101                    //naval sector guaranteed
  102                    if(nearTiles > 4){
  103                        Log.info("Sector {0} has {1} water tiles at {2} {3} -> naval", sector.id, nearTiles, cx, cy);
  104                        waterFloors = totalFloors;
  105                    }
  106    
  107                    //sort counts in descending order
  108                    Array<ObjectIntMap.Entry<Block>> entries = floors.entries().toArray();
  109                    entries.sort(e -> -e.value);
  110                    //remove all blocks occuring < 30 times - unimportant
  111                    entries.removeAll(e -> e.value < 30);
  112    
  113                    data.floors = new Block[entries.size];
  114                    data.floorCounts = new int[entries.size];
  115                    for(int i = 0; i < entries.size; i++){
  116                        data.floorCounts[i] = entries.get(i).value;
  117                        data.floors[i] = entries.get(i).key;
  118                    }
      ...
```
Post-state:
```java
      ...
   78                        }
   79                    }
   80    
   81                    CoreEntity entity = Team.sharded.core();
   82                    int cx = entity.tileX(), cy = entity.tileY();
   83    
   84                    int nearTiles = 0;
   85                    int waterCheckRad = 5;
   86    
   87                    //check for water presence
   88                    for(int rx = -waterCheckRad; rx <= waterCheckRad; rx++){
   89                        for(int ry = -waterCheckRad; ry <= waterCheckRad; ry++){
   90                            Tile tile = world.tile(cx + rx, cy + ry);
   91                            if(tile == null || tile.floor().liquidDrop != null){
   92                                nearTiles ++;
   93                            }
   94                        }
   95                    }
   96    
   97                    if(waterFloors / totalFloors >= 0.6f){
   98 >>                     Log.debug("Sector {0} has {1}/{2} water -> naval", sector.id, waterFloors, totalFloors);
   99                    }
  100    
  101                    //naval sector guaranteed
  102                    if(nearTiles > 4){
  103                        Log.debug("Sector {0} has {1} water tiles at {2} {3} -> naval", sector.id, nearTiles, cx, cy);
  104                        waterFloors = totalFloors;
  105                    }
  106    
  107                    //sort counts in descending order
  108                    Array<ObjectIntMap.Entry<Block>> entries = floors.entries().toArray();
  109                    entries.sort(e -> -e.value);
  110                    //remove all blocks occuring < 30 times - unimportant
  111                    entries.removeAll(e -> e.value < 30);
  112    
  113                    data.floors = new Block[entries.size];
  114                    data.floorCounts = new int[entries.size];
  115                    for(int i = 0; i < entries.size; i++){
  116                        data.floorCounts[i] = entries.get(i).value;
  117                        data.floors[i] = entries.get(i).key;
  118                    }
      ...
```

## Mindustry:76aa409f89b6:1 — CHANGE_LEVEL

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/76aa409f89b6a81166f69571463e26b5d73448cd
- method: `NetServer.sendWorldData(Player,int)` in `core/src/io/anuke/mindustry/core/NetServer.java`
- statement: `Log.info("Packed {0} compressed bytes of world data.", stream.size())` -> `Log.debug("Packed {0} compressed bytes of world data.", stream.size())`
- levels: INFO -> DEBUG

Pre-state:
```java
  229    public void sendWorldData(Player player, int clientID){
  230            ByteArrayOutputStream stream = new ByteArrayOutputStream();
  231            DeflaterOutputStream def = new DeflaterOutputStream(stream);
  232            NetworkIO.writeWorld(player, def);
  233            WorldStream data = new WorldStream();
  234            data.stream = new ByteArrayInputStream(stream.toByteArray());
  235            Net.sendStream(clientID, data);
  236    
  237 >>         Log.info("Packed {0} compressed bytes of world data.", stream.size());
  238        }
```
Post-state:
```java
  229    public void sendWorldData(Player player, int clientID){
  230            ByteArrayOutputStream stream = new ByteArrayOutputStream();
  231            DeflaterOutputStream def = new DeflaterOutputStream(stream);
  232            NetworkIO.writeWorld(player, def);
  233            WorldStream data = new WorldStream();
  234            data.stream = new ByteArrayInputStream(stream.toByteArray());
  235            Net.sendStream(clientID, data);
  236    
  237 >>         Log.debug("Packed {0} compressed bytes of world data.", stream.size());
  238        }
```

## Mindustry:2165a2af7d7d:1 — CHANGE_LEVEL

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/2165a2af7d7d179daa9c737e03d01de1929bb793
- method: `SectorDataGenerator.main(String[])` in `tools/src/mindustry/tools/SectorDataGenerator.java`
- statement: `Log.info("Sector {0} has {1} water tiles at {2} {3} -> naval", sector.id, nearTiles, cx, cy)` -> `Log.debug("Sector {0} has {1} water tiles at {2} {3} -> naval", sector.id, nearTiles, cx, cy)`
- levels: INFO -> DEBUG

Pre-state:
```java
      ...
   83    
   84                    int nearTiles = 0;
   85                    int waterCheckRad = 5;
   86    
   87                    //check for water presence
   88                    for(int rx = -waterCheckRad; rx <= waterCheckRad; rx++){
   89                        for(int ry = -waterCheckRad; ry <= waterCheckRad; ry++){
   90                            Tile tile = world.tile(cx + rx, cy + ry);
   91                            if(tile == null || tile.floor().liquidDrop != null){
   92                                nearTiles ++;
   93                            }
   94                        }
   95                    }
   96    
   97                    if(waterFloors / totalFloors >= 0.6f){
   98                        Log.info("Sector {0} has {1}/{2} water -> naval", sector.id, waterFloors, totalFloors);
   99                    }
  100    
  101                    //naval sector guaranteed
  102                    if(nearTiles > 4){
  103 >>                     Log.info("Sector {0} has {1} water tiles at {2} {3} -> naval", sector.id, nearTiles, cx, cy);
  104                        waterFloors = totalFloors;
  105                    }
  106    
  107                    //sort counts in descending order
  108                    Array<ObjectIntMap.Entry<Block>> entries = floors.entries().toArray();
  109                    entries.sort(e -> -e.value);
  110                    //remove all blocks occuring < 30 times - unimportant
  111                    entries.removeAll(e -> e.value < 30);
  112    
  113                    data.floors = new Block[entries.size];
  114                    data.floorCounts = new int[entries.size];
  115                    for(int i = 0; i < entries.size; i++){
  116                        data.floorCounts[i] = entries.get(i).value;
  117                        data.floors[i] = entries.get(i).key;
  118                    }
  119    
  120                    data.resources = content.asArray().sort(Structs.comps(Structs.comparing(Content::getContentType), Structs.comparingInt(c -> c.id))).toArray(UnlockableContent.class);
  121    
  122                    //50% water -> naval attribute
  123                    if(waterFloors / totalFloors >= 0.6f){
      ...
```
Post-state:
```java
      ...
   83    
   84                    int nearTiles = 0;
   85                    int waterCheckRad = 5;
   86    
   87                    //check for water presence
   88                    for(int rx = -waterCheckRad; rx <= waterCheckRad; rx++){
   89                        for(int ry = -waterCheckRad; ry <= waterCheckRad; ry++){
   90                            Tile tile = world.tile(cx + rx, cy + ry);
   91                            if(tile == null || tile.floor().liquidDrop != null){
   92                                nearTiles ++;
   93                            }
   94                        }
   95                    }
   96    
   97                    if(waterFloors / totalFloors >= 0.6f){
   98                        Log.debug("Sector {0} has {1}/{2} water -> naval", sector.id, waterFloors, totalFloors);
   99                    }
  100    
  101                    //naval sector guaranteed
  102                    if(nearTiles > 4){
  103 >>                     Log.debug("Sector {0} has {1} water tiles at {2} {3} -> naval", sector.id, nearTiles, cx, cy);
  104                        waterFloors = totalFloors;
  105                    }
  106    
  107                    //sort counts in descending order
  108                    Array<ObjectIntMap.Entry<Block>> entries = floors.entries().toArray();
  109                    entries.sort(e -> -e.value);
  110                    //remove all blocks occuring < 30 times - unimportant
  111                    entries.removeAll(e -> e.value < 30);
  112    
  113                    data.floors = new Block[entries.size];
  114                    data.floorCounts = new int[entries.size];
  115                    for(int i = 0; i < entries.size; i++){
  116                        data.floorCounts[i] = entries.get(i).value;
  117                        data.floors[i] = entries.get(i).key;
  118                    }
  119    
  120                    data.resources = content.asArray().sort(Structs.comps(Structs.comparing(Content::getContentType), Structs.comparingInt(c -> c.id))).toArray(UnlockableContent.class);
  121    
  122                    //50% water -> naval attribute
  123                    if(waterFloors / totalFloors >= 0.6f){
      ...
```

## subspace-infinity:bba6d636ded5:5 — CHANGE_LEVEL

- repo: subspace-infinity  commit: https://github.com/assofohdz/subspace-infinity/commit/bba6d636ded5c93e119a9948a81e13b2679c6b60
- method: `AccountClientService.AccountSessionCallback.notifyLoginStatus(boolean)` in `subspace-infinity/src/main/java/infinity/net/client/AccountClientService.java`
- statement: `log.trace("notifyLoginStatus(" + loggedIn + ")")` -> `log.info("notifyLoginStatus(" + loggedIn + ")")`
- levels: TRACE -> INFO

Pre-state:
```java
  125    @Override   
  126            public void notifyLoginStatus( boolean loggedIn ) {
  127 >>             log.trace("notifyLoginStatus(" + loggedIn + ")");
  128                listeners.forEach((l) -> {
  129                    l.notifyLoginStatus(loggedIn);
  130                });
  131            }
```
Post-state:
```java
  126    @Override   
  127            public void notifyLoginStatus( boolean loggedIn ) {
  128 >>             log.info("notifyLoginStatus(" + loggedIn + ")");
  129                listeners.forEach((l) -> {
  130                    l.notifyLoginStatus(loggedIn);
  131                });
  132            }
```

## Mindustry:9f4d44f0f337:2 — CHANGE_LEVEL

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/9f4d44f0f337db0f6a222fdcc00226037847bac7
- method: `Scripts.Scripts()` in `core/src/io/anuke/mindustry/mod/Scripts.java`
- statement: `Log.info("Time to load script engine: {0}", Time.elapsed())` -> `Log.debug("Time to load script engine: {0}", Time.elapsed())`
- levels: INFO -> DEBUG

Pre-state:
```java
   19    public Scripts(){
   20            Time.mark();
   21    
   22            context = Vars.platform.getScriptContext();
   23            context.setClassShutter(type -> (ClassAccess.allowedClassNames.contains(type) || type.startsWith("adapter") || type.contains("PrintStream") || type.startsWith("io.anuke.mindustry")) && !type.equals("io.anuke.mindustry.mod.ClassAccess"));
   24    
   25            scope = new ImporterTopLevel(context);
   26            wrapper = Core.files.internal("scripts/wrapper.js").readString();
   27    
   28            run(Core.files.internal("scripts/global.js").readString(), "global.js");
   29 >>         Log.info("Time to load script engine: {0}", Time.elapsed());
   30        }
```
Post-state:
```java
   19    public Scripts(){
   20            Time.mark();
   21    
   22            context = Vars.platform.getScriptContext();
   23            context.setClassShutter(type -> (ClassAccess.allowedClassNames.contains(type) || type.startsWith("adapter") || type.contains("PrintStream") || type.startsWith("io.anuke.mindustry")) && !type.equals("io.anuke.mindustry.mod.ClassAccess"));
   24    
   25            scope = new ImporterTopLevel(context);
   26            wrapper = Core.files.internal("scripts/wrapper.js").readString();
   27    
   28            run(Core.files.internal("scripts/global.js").readString(), "global.js");
   29 >>         Log.debug("Time to load script engine: {0}", Time.elapsed());
   30        }
```

## riiablo:d8570e136d8a:32 — CHANGE_LEVEL

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/d8570e136d8ad4c7ed344d98b9a59ddacd777b70
- method: `TxtParser.TxtParser(InputStream,int)` in `core/src/main/java/com/riiablo/excel/TxtParser.java`
- statement: `log.debug("columnIds: {}", columnIds)` -> `log.trace("columnIds: {}", columnIds)`
- levels: DEBUG -> TRACE

Pre-state:
```java
   49    private TxtParser(BufferedReader reader) throws IOException {
   50        this.reader = reader;
   51        line = reader.readLine();
   52        columnNames = StringUtils.splitPreserveAllTokens(line, '\t');
   53        log.debug("columnNames: {}", (Object) columnNames);
   54    
   55        columnIds = new ObjectIntMap<>();
   56        for (int i = 0; i < columnNames.length; i++) {
   57          String key = columnNames[i].toLowerCase();
   58          if (!columnIds.containsKey(key)) columnIds.put(key, i);
   59        }
   60 >>     log.debug("columnIds: {}", columnIds);
   61      }
```
Post-state:
```java
   59    TxtParser(InputStream in, int bufferSize) throws IOException {
   60        this.in = IOUtils.buffer(in, bufferSize);
   61    
   62        cache = new ByteArray(512);
   63        columnNames = new Array<>();
   64        columnIds = new ObjectIntMap<>();
   65        numColumns = parseColumnNames();
   66    
   67        log.info("numColumns: {}", numColumns);
   68        log.debug("columnNames: {}", columnNames);
   69 >>     log.trace("columnIds: {}", columnIds);
   70    
   71        tokenOffsets = new IntArray();
   72      }
```

## riiablo:d8472970323f:0 — CHANGE_LEVEL

- repo: riiablo  commit: https://github.com/collinsmith/riiablo/commit/d8472970323f2ab3cdf57206feb21fd9167a723f
- method: `Tool.handleCliError(String,Options,Throwable)` in `tools/src/main/java/com/riiablo/tool/Tool.java`
- statement: `log.error(t.getMessage(), t)` -> `log.debug(t.getMessage(), t)`
- levels: ERROR -> DEBUG

Pre-state:
```java
   32    protected void handleCliError(String cmd, Options options, Throwable t) {
   33 >>     log.error(t.getMessage(), t);
   34        System.out.println(ExceptionUtils.getRootCauseMessage(t));
   35        printHelp(cmd, options);
   36        System.exit(0);
   37      }
```
Post-state:
```java
   32    protected void handleCliError(String cmd, Options options, Throwable t) {
   33        if (t instanceof ParseException) {
   34 >>       log.debug(t.getMessage(), t);
   35        } else {
   36          log.fatal(t.getMessage(), t);
   37        }
   38    
   39        System.out.println(ExceptionUtils.getRootCauseMessage(t));
   40        printHelp(cmd, options);
   41        System.exit(0);
   42      }
```

## OpenRTS:e37d2e75e8a3:0 — CHANGE_LEVEL

- repo: OpenRTS  commit: https://github.com/methusalah/OpenRTS/commit/e37d2e75e8a3d37d3a34cd6c7287d3c44353256a
- method: `Cliff.getConnexionConfiguration()` in `RTSEclipseProject/src/model/battlefield/map/cliff/Cliff.java`
- statement: `LogUtil.logger.info("asking connexion conf but no connexion for cliff at "+tile.getCoord())` -> `LogUtil.logger.warning("asking connexion conf but no connexion for cliff at "+tile.getCoord())`
- levels: INFO -> WARN

Pre-state:
```java
   47    public String getConnexionConfiguration(){
   48            String res = new String();
   49            if(isNeighborCliff(tile.n))
   50                res = res.concat("n");
   51            if(isNeighborCliff(tile.s))
   52                res = res.concat("s");
   53            if(isNeighborCliff(tile.e))
   54                res = res.concat("e");
   55            if(isNeighborCliff(tile.w))
   56                res = res.concat("w");
   57            if(res.isEmpty())
   58 >>         	LogUtil.logger.info("asking connexion conf but no connexion for cliff at "+tile.getCoord());
   59            return res;
   60        }
```
Post-state:
```java
   36    public String getConnexionConfiguration(){
   37            String res = new String();
   38            if(isNeighborCliff(tile.n))
   39                res = res.concat("n");
   40            if(isNeighborCliff(tile.s))
   41                res = res.concat("s");
   42            if(isNeighborCliff(tile.e))
   43                res = res.concat("e");
   44            if(isNeighborCliff(tile.w))
   45                res = res.concat("w");
   46            if(res.isEmpty())
   47 >>         	LogUtil.logger.warning("asking connexion conf but no connexion for cliff at "+tile.getCoord());
   48            return res;
   49        }
```

## Mindustry:205c4e723ab2:34 — CHANGE_LEVEL

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/205c4e723ab2796480d5b3c401eeabf2c1644832
- method: `Net.showError(String)` in `core/src/io/anuke/mindustry/net/Net.java`
- statement: `UCore.log(text)` -> `Log.err(text)`
- levels: INFO -> ERROR

Pre-state:
```java
   36    public static void showError(String text){
   37    		if(!headless){
   38    			ui.showError(text);
   39    		}else{
   40 >> 			UCore.log(text);
   41    		}
   42    	}
```
Post-state:
```java
   37    public static void showError(String text){
   38    		if(!headless){
   39    			ui.showError(text);
   40    		}else{
   41 >> 			Log.err(text);
   42    		}
   43    	}
```

## Mindustry:b1e8001ae805:0 — CHANGE_LEVEL

- repo: Mindustry  commit: https://github.com/Anuken/Mindustry/commit/b1e8001ae8055553f7aa7f3f71c683625293af94
- method: `MenuRenderer.MenuRenderer()` in `core/src/mindustry/graphics/MenuRenderer.java`
- statement: `Log.info("Time to generate menu: @", Time.elapsed())` -> `Log.debug("Time to generate menu: @", Time.elapsed())`
- levels: INFO -> DEBUG

Pre-state:
```java
   35    public MenuRenderer(){
   36            Time.mark();
   37            generate();
   38            cache();
   39 >>         Log.info("Time to generate menu: @", Time.elapsed());
   40        }
```
Post-state:
```java
   35    public MenuRenderer(){
   36            Time.mark();
   37            generate();
   38            cache();
   39 >>         Log.debug("Time to generate menu: @", Time.elapsed());
   40        }
```
