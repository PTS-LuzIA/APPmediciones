"""
Proyecto Routes
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import sys
from pathlib import Path
import hashlib
import shutil

sys.path.append(str(Path(__file__).parent.parent.parent))

from api.dependencies import get_db, get_current_user, get_database_manager
from api.schemas.proyecto import (
    ProyectoCreate,
    ProyectoUpdate,
    ProyectoResponse,
    ProyectoCompleto,
    ProyectoArbol,
    EstadisticasProyecto
)
from database.manager import DatabaseManager
from database.queries import QueryHelper
from models import Usuario
from services.proyecto_service import ProyectoService
from services.procesamiento_service import ProcesamientoService
from config import settings

router = APIRouter()


@router.get("", response_model=List[ProyectoResponse])
async def listar_proyectos(
    skip: int = 0,
    limit: int = 100,
    current_user: Usuario = Depends(get_current_user),
    manager: DatabaseManager = Depends(get_database_manager)
):
    """
    List all projects for current user.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        current_user: Current authenticated user
        manager: Database manager

    Returns:
        List of projects
    """
    proyectos = manager.listar_proyectos(current_user.id, offset=skip, limite=limit)
    return [ProyectoResponse.model_validate(p) for p in proyectos]


@router.post("", response_model=ProyectoResponse, status_code=status.HTTP_201_CREATED)
async def crear_proyecto(
    proyecto_data: ProyectoCreate,
    current_user: Usuario = Depends(get_current_user),
    manager: DatabaseManager = Depends(get_database_manager)
):
    """
    Create a new project.

    Args:
        proyecto_data: Project creation data
        current_user: Current authenticated user
        manager: Database manager

    Returns:
        Created project
    """
    proyecto = manager.crear_proyecto(
        usuario_id=current_user.id,
        nombre=proyecto_data.nombre,
        descripcion=proyecto_data.descripcion
    )
    return ProyectoResponse.model_validate(proyecto)


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    current_user: Usuario = Depends(get_current_user),
    manager: DatabaseManager = Depends(get_database_manager)
):
    """
    Upload a PDF file and create a new project.

    Args:
        file: PDF file to upload
        current_user: Current authenticated user
        manager: Database manager

    Returns:
        dict with proyecto_id

    Raises:
        HTTPException: If file is not a PDF or exceeds size limit
    """
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are allowed"
        )

    # Read file content
    file_content = await file.read()

    # Validate file size
    if len(file_content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed ({settings.MAX_UPLOAD_SIZE / 1024 / 1024} MB)"
        )

    # Calculate file hash
    file_hash = hashlib.md5(file_content).hexdigest()

    # Create project name from filename
    proyecto_nombre = file.filename.replace('.pdf', '')

    # Create project first to get proyecto_id
    proyecto = manager.crear_proyecto(
        usuario_id=current_user.id,
        nombre=proyecto_nombre,
        descripcion=f"Proyecto creado desde PDF: {file.filename}"
    )

    # Save file with proyecto_id instead of hash
    file_path = settings.UPLOADS_DIR / f"u{current_user.id}_p{proyecto.id}_{file.filename}"
    with open(file_path, 'wb') as f:
        f.write(file_content)

    # Update project with PDF info
    from models import Proyecto
    proyecto_obj = manager.session.query(Proyecto).filter_by(id=proyecto.id).first()
    if proyecto_obj:
        proyecto_obj.pdf_path = str(file_path)
        proyecto_obj.pdf_nombre = file.filename
        proyecto_obj.pdf_hash = file_hash
        manager.session.commit()

    # Return upload success without processing
    # User will manually execute phases 1-4 via /api/procesamiento endpoints
    return {
        "proyecto_id": proyecto.id,
        "nombre": proyecto.nombre,
        "pdf_nombre": file.filename,
        "pdf_path": str(file_path),
        "message": "PDF uploaded successfully. Ready for processing."
    }


@router.get("/{proyecto_id}")
async def obtener_proyecto(
    proyecto_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a project by ID with full tree structure.

    Args:
        proyecto_id: Project ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Project with complete tree structure

    Raises:
        HTTPException: If project not found or user doesn't have access
    """
    service = ProyectoService(db)
    resultado = service.obtener_proyecto_completo(proyecto_id)

    if not resultado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    proyecto_obj = resultado["proyecto"]
    arbol = resultado.get("arbol", [])
    estadisticas = resultado.get("estadisticas", {})

    # Check user has access
    if proyecto_obj.usuario_id != current_user.id and not current_user.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this project"
        )

    # Return response with complete tree
    return {
        "id": proyecto_obj.id,
        "usuario_id": proyecto_obj.usuario_id,
        "nombre": proyecto_obj.nombre,
        "descripcion": proyecto_obj.descripcion,
        "pdf_path": proyecto_obj.pdf_path,
        "fase_actual": proyecto_obj.fase_actual,
        "presupuesto_total": float(proyecto_obj.presupuesto_total or 0),
        "fecha_creacion": proyecto_obj.fecha_creacion.isoformat(),
        "fecha_actualizacion": proyecto_obj.fecha_actualizacion.isoformat(),
        "tiene_mediciones_auxiliares": False,  # TODO: implement
        "num_capitulos": estadisticas.get("num_capitulos", 0),
        "capitulos": arbol  # Include full tree structure
    }


@router.get("/{proyecto_id}/stats")
async def obtener_estadisticas_proyecto(
    proyecto_id: int,
    current_user: Usuario = Depends(get_current_user),
    manager: DatabaseManager = Depends(get_database_manager)
):
    """
    Get project statistics.

    Args:
        proyecto_id: Project ID
        current_user: Current authenticated user
        manager: Database manager

    Returns:
        Project statistics (simplified for frontend)

    Raises:
        HTTPException: If project not found or user doesn't have access
    """
    proyecto = manager.obtener_proyecto(proyecto_id)

    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Check user has access
    if proyecto.usuario_id != current_user.id and not current_user.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this project"
        )

    # Get statistics from database
    query_helper = QueryHelper(manager.session)
    estadisticas = query_helper.obtener_estadisticas_proyecto(proyecto_id)

    # Contar mediciones
    from sqlalchemy import text
    result = manager.session.execute(
        text("SELECT COUNT(*) FROM appmediciones.mediciones WHERE concepto_id IN (SELECT id FROM appmediciones.conceptos WHERE proyecto_id = :pid)"),
        {"pid": proyecto_id}
    )
    num_mediciones = result.scalar() or 0

    # Return simplified stats matching frontend expectations
    return {
        "total_capitulos": estadisticas.get("num_capitulos", 0),
        "total_subcapitulos": estadisticas.get("num_subcapitulos", 0),
        "total_partidas": estadisticas.get("num_partidas", 0),
        "partidas_con_mediciones": num_mediciones,
        "presupuesto_total": float(proyecto.presupuesto_total or 0)
    }


@router.put("/{proyecto_id}", response_model=ProyectoResponse)
async def actualizar_proyecto(
    proyecto_id: int,
    proyecto_update: ProyectoUpdate,
    current_user: Usuario = Depends(get_current_user),
    manager: DatabaseManager = Depends(get_database_manager)
):
    """
    Update a project.

    Args:
        proyecto_id: Project ID
        proyecto_update: Project update data
        current_user: Current authenticated user
        manager: Database manager

    Returns:
        Updated project

    Raises:
        HTTPException: If project not found or user doesn't have access
    """
    proyecto = manager.obtener_proyecto(proyecto_id)

    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Check user has access
    if proyecto.usuario_id != current_user.id and not current_user.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this project"
        )

    # Update project
    updated_proyecto = manager.actualizar_proyecto(
        proyecto_id,
        nombre=proyecto_update.nombre,
        descripcion=proyecto_update.descripcion,
        fase_actual=proyecto_update.fase_actual,
        total_presupuesto=proyecto_update.total_presupuesto
    )

    return ProyectoResponse.model_validate(updated_proyecto)


@router.delete("/{proyecto_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_proyecto(
    proyecto_id: int,
    current_user: Usuario = Depends(get_current_user),
    manager: DatabaseManager = Depends(get_database_manager)
):
    """
    Delete a project.

    Args:
        proyecto_id: Project ID
        current_user: Current authenticated user
        manager: Database manager

    Raises:
        HTTPException: If project not found or user doesn't have access
    """
    proyecto = manager.obtener_proyecto(proyecto_id)

    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Check user has access
    if proyecto.usuario_id != current_user.id and not current_user.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this project"
        )

    manager.eliminar_proyecto(proyecto_id)
    return None


@router.get("/{proyecto_id}/arbol", response_model=ProyectoArbol)
async def obtener_arbol_proyecto(
    proyecto_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get complete project tree structure.

    Args:
        proyecto_id: Project ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Project with complete tree

    Raises:
        HTTPException: If project not found or user doesn't have access
    """
    manager = DatabaseManager(db)
    proyecto = manager.obtener_proyecto(proyecto_id)

    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Check user has access
    if proyecto.usuario_id != current_user.id and not current_user.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this project"
        )

    # Get tree
    query_helper = QueryHelper(db)
    arbol = query_helper.obtener_arbol_completo(proyecto_id)

    return ProyectoArbol(
        proyecto=ProyectoResponse.model_validate(proyecto),
        arbol=arbol
    )


@router.get("/{proyecto_id}/estadisticas", response_model=EstadisticasProyecto)
async def obtener_estadisticas_proyecto(
    proyecto_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get project statistics.

    Args:
        proyecto_id: Project ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Project statistics

    Raises:
        HTTPException: If project not found or user doesn't have access
    """
    manager = DatabaseManager(db)
    proyecto = manager.obtener_proyecto(proyecto_id)

    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Check user has access
    if proyecto.usuario_id != current_user.id and not current_user.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this project"
        )

    # Get statistics
    query_helper = QueryHelper(db)
    stats = query_helper.obtener_estadisticas_proyecto(proyecto_id)

    return EstadisticasProyecto(**stats)


@router.post("/{proyecto_id}/resolver-discrepancia")
async def resolver_discrepancia(
    proyecto_id: int,
    tipo: str,
    elemento_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Resolve a single discrepancy using AI to find missing partidas.

    Args:
        proyecto_id: Project ID
        tipo: Type of element ('capitulo' or 'subcapitulo')
        elemento_id: ID of the element (nodo) with discrepancy
        current_user: Current authenticated user
        db: Database session

    Returns:
        Resolution result with suggested partidas

    Raises:
        HTTPException: If project not found, user doesn't have access, or resolution fails
    """
    from services.ia_service import get_ia_service
    from sqlalchemy import text
    import logging

    logger = logging.getLogger(__name__)
    manager = DatabaseManager(db)

    # Verify access
    proyecto = manager.obtener_proyecto(proyecto_id)
    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    if proyecto.usuario_id != current_user.id and not current_user.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this project"
        )

    # Get element information
    elemento = db.execute(
        text("""
            SELECT n.id, n.nivel, c.codigo, c.nombre, c.tipo, c.total
            FROM appmediciones.nodos n
            INNER JOIN appmediciones.conceptos c ON n.codigo_concepto = c.codigo
                AND c.proyecto_id = n.proyecto_id
            WHERE n.id = :elemento_id AND n.proyecto_id = :pid
        """),
        {'elemento_id': elemento_id, 'pid': proyecto_id}
    ).fetchone()

    if not elemento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Element with ID {elemento_id} not found"
        )

    codigo = elemento[2]
    nombre = elemento[3]
    total_esperado = float(elemento[5] or 0.0)

    # Get existing partidas
    partidas_existentes = db.execute(
        text("""
            SELECT c.codigo, c.nombre as resumen, c.unidad, n.cantidad, c.precio,
                   (n.cantidad * c.precio) as importe
            FROM appmediciones.nodos n
            INNER JOIN appmediciones.conceptos c ON n.codigo_concepto = c.codigo
                AND c.proyecto_id = :pid
            WHERE n.padre_id = :elemento_id AND c.tipo = 'PARTIDA'
        """),
        {'elemento_id': elemento_id, 'pid': proyecto_id}
    ).fetchall()

    partidas_list = [
        {
            'codigo': p[0],
            'resumen': p[1],
            'unidad': p[2],
            'cantidad': float(p[3] or 0.0),
            'precio': float(p[4] or 0.0),
            'importe': float(p[5] or 0.0)
        }
        for p in partidas_existentes
    ]

    total_calculado = sum(p['importe'] for p in partidas_list)
    diferencia = total_esperado - total_calculado

    # Get extracted text from PDF
    # Buscar archivo de texto extraído en el directorio de logs
    extracted_dir = Path(settings.LOGS_DIR) / "extracted_pdfs"
    texto_pdf = ""

    # Buscar archivo que coincida con el patrón u{user_id}_p{proyecto_id}_*_extracted.txt
    patron = f"u{proyecto.usuario_id}_p{proyecto_id}_*_extracted.txt"
    archivos_coincidentes = list(extracted_dir.glob(patron))

    if archivos_coincidentes:
        # Usar el primer archivo encontrado (debería ser único)
        pdf_text_file = archivos_coincidentes[0]
        with open(pdf_text_file, 'r', encoding='utf-8') as f:
            texto_pdf = f.read()
        logger.info(f"✓ Texto extraído cargado desde: {pdf_text_file}")
    else:
        # Si no existe, intentar extraer el PDF ahora
        if proyecto.pdf_path and Path(proyecto.pdf_path).exists():
            from parsers.pdf_extractor import PDFExtractor
            try:
                extractor = PDFExtractor(
                    proyecto.pdf_path,
                    proyecto.usuario_id,
                    proyecto_id
                )
                datos = extractor.extraer_todo()
                texto_pdf = datos.get('all_text', '')
                logger.info(f"✓ Texto extraído del PDF en tiempo real: {len(texto_pdf)} caracteres")
            except Exception as e:
                logger.error(f"Error extrayendo texto del PDF: {e}")
                texto_pdf = ""
        else:
            logger.warning(f"No se encontró texto extraído del PDF para proyecto {proyecto_id}")

    # Use AI service to analyze discrepancy
    ia_service = get_ia_service()
    resultado = ia_service.analizar_discrepancia(
        codigo=codigo,
        nombre=nombre,
        tipo=tipo,
        total_esperado=total_esperado,
        total_calculado=total_calculado,
        diferencia=diferencia,
        partidas_existentes=partidas_list,
        texto_pdf=texto_pdf
    )

    if not resultado['exito']:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI analysis failed: {resultado.get('error', 'Unknown error')}"
        )

    # Guardar partidas sugeridas en la base de datos
    partidas_guardadas = 0
    partidas_sugeridas = resultado.get('partidas_sugeridas', [])

    if partidas_sugeridas:
        from models.concepto import Concepto, TipoConcepto
        from models.nodo import Nodo

        # Obtener el máximo orden actual de los hijos
        max_orden_result = db.execute(
            text("""
                SELECT COALESCE(MAX(orden), 0) as max_orden
                FROM appmediciones.nodos
                WHERE padre_id = :padre_id
            """),
            {'padre_id': elemento_id}
        ).fetchone()
        orden_actual = max_orden_result[0] if max_orden_result else 0

        # Obtener nivel del nodo padre
        nivel_padre = elemento[1]  # nivel está en posición 1 del SELECT

        for partida in partidas_sugeridas:
            try:
                codigo_partida = partida.get('codigo', '')
                if not codigo_partida:
                    continue

                # Verificar si el concepto ya existe
                concepto_existente = db.execute(
                    text("""
                        SELECT id FROM appmediciones.conceptos
                        WHERE proyecto_id = :pid AND codigo = :codigo
                    """),
                    {'pid': proyecto_id, 'codigo': codigo_partida}
                ).fetchone()

                if not concepto_existente:
                    # Crear concepto solo si no existe
                    nuevo_concepto = Concepto(
                        proyecto_id=proyecto_id,
                        codigo=codigo_partida,
                        tipo=TipoConcepto.PARTIDA,
                        nombre=partida.get('resumen', partida.get('descripcion', codigo_partida))[:500],
                        resumen=partida.get('resumen', '')[:500],
                        descripcion=partida.get('descripcion', ''),
                        unidad=partida.get('unidad', 'ud')[:20],
                        precio=partida.get('precio', 0),
                        cantidad_total=0,  # Se calculará sumando todos los nodos
                        importe_total=0    # Se calculará sumando todos los nodos
                    )
                    db.add(nuevo_concepto)
                    db.flush()  # Para obtener el ID
                    logger.info(f"✓ Concepto {codigo_partida} creado")
                else:
                    logger.info(f"✓ Concepto {codigo_partida} ya existe, reutilizando...")

                # Verificar si ya existe un nodo para este concepto en este padre
                nodo_existente = db.execute(
                    text("""
                        SELECT id FROM appmediciones.nodos
                        WHERE proyecto_id = :pid
                            AND padre_id = :padre_id
                            AND codigo_concepto = :codigo
                    """),
                    {'pid': proyecto_id, 'padre_id': elemento_id, 'codigo': codigo_partida}
                ).fetchone()

                if nodo_existente:
                    logger.info(f"⚠ Partida {codigo_partida} ya existe en este subcapítulo, saltando...")
                    continue

                # Crear nodo solo si no existe en este padre
                orden_actual += 1
                nuevo_nodo = Nodo(
                    proyecto_id=proyecto_id,
                    padre_id=elemento_id,
                    codigo_concepto=codigo_partida,
                    nivel=nivel_padre + 1,
                    orden=orden_actual,
                    cantidad=partida.get('cantidad', 1)
                )
                db.add(nuevo_nodo)

                partidas_guardadas += 1
                logger.info(f"✓ Partida {codigo_partida} agregada al subcapítulo")

            except Exception as e:
                logger.error(f"Error guardando partida {partida.get('codigo', '?')}: {e}")
                continue

        # Commit de los cambios
        try:
            db.commit()
            logger.info(f"✓ {partidas_guardadas} partidas guardadas en BD para {codigo}")
        except Exception as e:
            db.rollback()
            logger.error(f"Error en commit: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error saving partidas to database: {str(e)}"
            )

        # Actualizar totales de partidas (cantidad_total e importe_total)
        _actualizar_totales_partidas(db, proyecto_id)

        # Recalcular totales de capítulos/subcapítulos después de agregar partidas
        _recalcular_totales_concepto(db, proyecto_id, codigo)

    return {
        'codigo': codigo,
        'nombre': nombre,
        'diferencia_original': diferencia,
        'partidas_agregadas': partidas_guardadas,
        'partidas_sugeridas_total': len(partidas_sugeridas),
        'total_agregado': resultado['total_sugerido'],
        'partidas_sugeridas': resultado['partidas_sugeridas'],
        'explicacion': resultado['explicacion']
    }


@router.post("/{proyecto_id}/resolver-discrepancias-bulk")
async def resolver_discrepancias_bulk(
    proyecto_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Resolve all discrepancies in a project using AI.

    Args:
        proyecto_id: Project ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Bulk resolution results

    Raises:
        HTTPException: If project not found or user doesn't have access
    """
    from services.procesamiento_service import ProcesamientoService
    import logging

    logger = logging.getLogger(__name__)
    manager = DatabaseManager(db)

    # Verify access
    proyecto = manager.obtener_proyecto(proyecto_id)
    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    if proyecto.usuario_id != current_user.id and not current_user.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this project"
        )

    if not proyecto.pdf_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No PDF file uploaded for this project"
        )

    # Execute Fase 3 to get discrepancies
    service = ProcesamientoService(db)
    try:
        resultado_fase3 = service.ejecutar_fase3(proyecto_id, proyecto.pdf_path)
        discrepancias = resultado_fase3.get('discrepancias', [])

        if not discrepancias:
            return {
                'resueltas_exitosas': 0,
                'resueltas_fallidas': 0,
                'total_partidas_agregadas': 0,
                'mensaje': 'No hay discrepancias para resolver',
                'errores': []
            }

        # Resolve each discrepancy
        resueltas_exitosas = 0
        resueltas_fallidas = 0
        total_partidas_agregadas = 0
        errores = []

        for disc in discrepancias:
            try:
                # Call individual resolution endpoint logic
                resultado = await resolver_discrepancia(
                    proyecto_id=proyecto_id,
                    tipo=disc['tipo'],
                    elemento_id=disc['id'],
                    current_user=current_user,
                    db=db
                )
                resueltas_exitosas += 1
                total_partidas_agregadas += resultado['partidas_agregadas']
            except Exception as e:
                resueltas_fallidas += 1
                errores.append(f"{disc['codigo']}: {str(e)}")
                logger.error(f"Error resolviendo discrepancia {disc['codigo']}: {e}")

        return {
            'resueltas_exitosas': resueltas_exitosas,
            'resueltas_fallidas': resueltas_fallidas,
            'total_partidas_agregadas': total_partidas_agregadas,
            'errores': errores
        }

    except Exception as e:
        logger.error(f"Error in bulk discrepancy resolution: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk resolution failed: {str(e)}"
        )


@router.get("/{proyecto_id}/discrepancias-db")
async def obtener_discrepancias_desde_bd(
    proyecto_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene discrepancias calculadas desde la base de datos en lugar de re-parsear el PDF.
    Útil después de resolver discrepancias para ver el estado actualizado.

    Args:
        proyecto_id: ID del proyecto
        current_user: Usuario autenticado actual
        db: Sesión de base de datos

    Returns:
        Lista de discrepancias calculadas desde la BD

    Raises:
        HTTPException: Si el proyecto no se encuentra o el usuario no tiene acceso
    """
    from sqlalchemy import text
    import logging

    logger = logging.getLogger(__name__)
    manager = DatabaseManager(db)

    # Verificar acceso
    proyecto = manager.obtener_proyecto(proyecto_id)
    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    if proyecto.usuario_id != current_user.id and not current_user.es_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this project"
        )

    # Primero recalcular todos los totales
    _recalcular_todos_los_totales(db, proyecto_id)

    # Obtener conceptos con discrepancias (capítulos y subcapítulos)
    discrepancias_query = db.execute(
        text("""
            SELECT
                n.id,
                c.codigo,
                c.nombre,
                c.tipo,
                c.total as total_pdf,
                c.total_calculado,
                ABS(COALESCE(c.total, 0) - COALESCE(c.total_calculado, 0)) as diferencia,
                CASE
                    WHEN COALESCE(c.total, 0) > 0 THEN
                        ABS(COALESCE(c.total, 0) - COALESCE(c.total_calculado, 0)) / c.total * 100
                    ELSE 0
                END as porcentaje
            FROM appmediciones.conceptos c
            INNER JOIN appmediciones.nodos n ON c.codigo = n.codigo_concepto
                AND c.proyecto_id = n.proyecto_id
            WHERE c.proyecto_id = :pid
                AND c.tipo IN ('CAPITULO', 'SUBCAPITULO')
                AND c.total IS NOT NULL
                AND c.total > 0
                AND ABS(COALESCE(c.total, 0) - COALESCE(c.total_calculado, 0)) / c.total * 100 > 0.1
            ORDER BY c.codigo
        """),
        {'pid': proyecto_id}
    ).fetchall()

    discrepancias = []
    total_original = 0.0
    total_calculado = 0.0

    for row in discrepancias_query:
        disc = {
            'id': row[0],
            'codigo': row[1],
            'nombre': row[2],
            'tipo': 'capitulo' if row[3] == 'CAPITULO' else 'subcapitulo',
            'total_original': float(row[4] or 0.0),
            'total_calculado': float(row[5] or 0.0),
            'diferencia': float(row[6] or 0.0)
        }
        discrepancias.append(disc)
        total_original += disc['total_original']
        total_calculado += disc['total_calculado']

    logger.info(f"✓ Discrepancias desde BD: {len(discrepancias)} encontradas")

    return {
        'num_discrepancias': len(discrepancias),
        'discrepancias': discrepancias,
        'total_original': total_original,
        'total_calculado': total_calculado
    }


def _recalcular_todos_los_totales(db: Session, proyecto_id: int):
    """
    Recalcula todos los totales del proyecto desde las hojas hacia la raíz.

    Args:
        db: Database session
        proyecto_id: ID del proyecto
    """
    from sqlalchemy import text
    import logging

    logger = logging.getLogger(__name__)

    try:
        # Obtener todos los conceptos ordenados por nivel descendente (hojas primero)
        conceptos = db.execute(
            text("""
                SELECT DISTINCT c.codigo, n.nivel
                FROM appmediciones.conceptos c
                INNER JOIN appmediciones.nodos n ON c.codigo = n.codigo_concepto
                    AND c.proyecto_id = n.proyecto_id
                WHERE c.proyecto_id = :pid
                    AND c.tipo IN ('CAPITULO', 'SUBCAPITULO')
                ORDER BY n.nivel DESC
            """),
            {'pid': proyecto_id}
        ).fetchall()

        logger.info(f"Recalculando totales para {len(conceptos)} conceptos...")

        for concepto in conceptos:
            codigo = concepto[0]

            # Calcular total_calculado (suma de hijos)
            # Redondear cada importe antes de sumar (método contable)
            db.execute(
                text("""
                    UPDATE appmediciones.conceptos c
                    SET total_calculado = (
                        SELECT COALESCE(SUM(CASE
                            WHEN c2.tipo = 'PARTIDA' THEN ROUND(n.cantidad * COALESCE(c2.precio, 0), 2)
                            ELSE c2.total_calculado
                        END), 0)
                        FROM appmediciones.nodos n
                        INNER JOIN appmediciones.conceptos c2
                            ON n.codigo_concepto = c2.codigo
                            AND c2.proyecto_id = n.proyecto_id
                        WHERE n.proyecto_id = :pid
                            AND n.padre_id = (
                                SELECT id FROM appmediciones.nodos
                                WHERE proyecto_id = :pid
                                    AND codigo_concepto = :codigo
                                LIMIT 1
                            )
                    )
                    WHERE c.proyecto_id = :pid AND c.codigo = :codigo
                """),
                {'pid': proyecto_id, 'codigo': codigo}
            )

        db.commit()
        logger.info("✓ Todos los totales recalculados")

    except Exception as e:
        logger.error(f"Error recalculando todos los totales: {e}")
        db.rollback()
        raise


def _actualizar_totales_partidas(db: Session, proyecto_id: int):
    """
    Actualiza cantidad_total e importe_total de todas las partidas.

    Para cada concepto de tipo PARTIDA:
    - cantidad_total = suma de n.cantidad de todos los nodos que usan ese concepto
    - importe_total = suma de (n.cantidad × c.precio) de todos los nodos

    Args:
        db: Database session
        proyecto_id: ID del proyecto
    """
    from sqlalchemy import text
    import logging

    logger = logging.getLogger(__name__)

    try:
        db.execute(
            text("""
                UPDATE appmediciones.conceptos c
                SET
                    cantidad_total = (
                        SELECT COALESCE(SUM(n.cantidad), 0)
                        FROM appmediciones.nodos n
                        WHERE n.proyecto_id = :pid
                            AND n.codigo_concepto = c.codigo
                    ),
                    importe_total = (
                        SELECT COALESCE(SUM(ROUND(n.cantidad * COALESCE(c.precio, 0), 2)), 0)
                        FROM appmediciones.nodos n
                        WHERE n.proyecto_id = :pid
                            AND n.codigo_concepto = c.codigo
                    )
                WHERE c.proyecto_id = :pid
                    AND c.tipo = 'PARTIDA'
            """),
            {'pid': proyecto_id}
        )

        db.commit()
        logger.info(f"  ✓ Totales de partidas actualizados")

    except Exception as e:
        logger.error(f"  ❌ Error actualizando totales de partidas: {e}")
        db.rollback()
        raise


def _recalcular_totales_concepto(db: Session, proyecto_id: int, codigo_concepto: str):
    """
    Recalcula el total_calculado de un concepto sumando sus partidas hijas.
    También actualiza recursivamente todos los conceptos padre hasta la raíz.

    Args:
        db: Database session
        proyecto_id: ID del proyecto
        codigo_concepto: Código del concepto a recalcular
    """
    from sqlalchemy import text
    import logging

    logger = logging.getLogger(__name__)

    try:
        # Recalcular total del concepto actual (suma de partidas hijas)
        # Redondear cada importe antes de sumar (método contable)
        resultado = db.execute(
            text("""
                UPDATE appmediciones.conceptos c
                SET total_calculado = (
                    SELECT COALESCE(SUM(CASE
                        WHEN c2.tipo = 'PARTIDA' THEN ROUND(n.cantidad * COALESCE(c2.precio, 0), 2)
                        ELSE c2.total_calculado
                    END), 0)
                    FROM appmediciones.nodos n
                    INNER JOIN appmediciones.conceptos c2
                        ON n.codigo_concepto = c2.codigo
                        AND c2.proyecto_id = n.proyecto_id
                    WHERE n.proyecto_id = :pid
                        AND n.padre_id = (
                            SELECT id FROM appmediciones.nodos
                            WHERE proyecto_id = :pid
                                AND codigo_concepto = :codigo
                            LIMIT 1
                        )
                )
                WHERE c.proyecto_id = :pid AND c.codigo = :codigo
                RETURNING c.total_calculado
            """),
            {'pid': proyecto_id, 'codigo': codigo_concepto}
        ).fetchone()

        if resultado:
            nuevo_total = float(resultado[0] or 0.0)
            logger.info(f"✓ Total recalculado para {codigo_concepto}: {nuevo_total:.2f}€")

            # Recalcular recursivamente los padres
            padre_result = db.execute(
                text("""
                    SELECT c.codigo
                    FROM appmediciones.nodos n
                    INNER JOIN appmediciones.nodos n_padre ON n.padre_id = n_padre.id
                    INNER JOIN appmediciones.conceptos c ON n_padre.codigo_concepto = c.codigo
                        AND c.proyecto_id = n_padre.proyecto_id
                    WHERE n.proyecto_id = :pid
                        AND n.codigo_concepto = :codigo
                        AND c.tipo != 'RAIZ'
                    LIMIT 1
                """),
                {'pid': proyecto_id, 'codigo': codigo_concepto}
            ).fetchone()

            if padre_result:
                codigo_padre = padre_result[0]
                logger.info(f"  ↑ Recalculando padre: {codigo_padre}")
                _recalcular_totales_concepto(db, proyecto_id, codigo_padre)

        db.commit()

    except Exception as e:
        logger.error(f"Error recalculando totales para {codigo_concepto}: {e}")
        db.rollback()
        raise
