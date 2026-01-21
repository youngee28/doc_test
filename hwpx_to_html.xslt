<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"
    xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core"
    xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"
    exclude-result-prefixes="hp hc hh">

    <xsl:output method="html" encoding="UTF-8" indent="yes" />

    <xsl:param name="header_path" />
    <xsl:param name="fonts_dir" />
    <xsl:param name="base_dir" />

    <xsl:template match="/">
        <html>
            <head>
                <meta charset="UTF-8" />
                <style> @font-face { font-family: 'Gulim'; src: url('<xsl:value-of
                        select="concat('file://', $fonts_dir, '/GulimChe.ttf')" />'); } @page {
        size: A4; margin: 20mm; } body { font-family: 'Gulim', 'GulimChe', sans-serif; line-height:
        1.6; font-size: 10pt; } p { margin: 0; padding: 0; white-space: pre-wrap; min-height:
        1.25em; clear: both; } .tab-spacer { display: inline-block; width: 2.2em; } img {
        vertical-align: middle; } </style>
            </head>
            <body>
                <xsl:apply-templates select="//hp:p" />
            </body>
        </html>
    </xsl:template>

    <xsl:template match="hp:p">
        <xsl:variable name="pId" select="@paraPrIDRef" />
        <xsl:variable name="paraPr"
            select="document($header_path)//hh:paraPr[@id=$pId]" />

        <!-- 계층 구조(hp:switch 등)와 관계없이 속성 추출 -->
        <xsl:variable name="alignNode"
            select="$paraPr//hh:align" />
        <xsl:variable name="marginNode" select="$paraPr//hh:margin" />

        <xsl:variable
            name="align">
            <xsl:choose>
                <xsl:when test="$alignNode/@horizontal = 'CENTER'">center</xsl:when>
                <xsl:when test="$alignNode/@horizontal = 'RIGHT'">right</xsl:when>
                <xsl:when test="$alignNode/@horizontal = 'JUSTIFY'">justify</xsl:when>
                <xsl:otherwise>left</xsl:otherwise>
            </xsl:choose>
        </xsl:variable>

        <!-- Margin/Intent 추출 (local-name으로 네임스페이스 이슈 방지) -->
        <xsl:variable
            name="lVal" select="number($marginNode/*[local-name()='left']/@value)" />
        <xsl:variable
            name="iVal" select="number($marginNode/*[local-name()='intent']/@value)" />

        <xsl:variable
            name="left" select="translate(string($lVal div 100), 'NaN', '0')" />
        <xsl:variable
            name="intent" select="translate(string($iVal div 100), 'NaN', '0')" />

        <!-- Unified Math: margin-left(전체 여백) = left + intent, text-indent(첫 줄 오프셋) = -intent -->
        <xsl:variable
            name="finalLeft" select="number($left) + number($intent)" />
        <xsl:variable
            name="finalIndent" select="-1 * number($intent)" />

        <p
            style="text-align: {$align}; margin-left: {$finalLeft}pt; text-indent: {$finalIndent}pt;"
            data-pId="{$pId}" data-left-raw="{$lVal}" data-intent-raw="{$iVal}">
            <xsl:apply-templates select="hp:run" />
        </p>
    </xsl:template>

    <xsl:template match="hp:run">
        <xsl:variable name="cId" select="@charPrIDRef" />
        <xsl:variable name="charPr"
            select="document($header_path)//hh:charPr[@id=$cId]" />
        
        <xsl:variable name="cStyle">
            <!-- 볼드 처리 -->
            <xsl:if
                test="$charPr/hh:bold or $charPr/@bold">font-weight: bold; </xsl:if>
            <!-- 밑줄 처리: type이 NONE이 아닐 때만 적용 -->
            <xsl:if
                test="$charPr/hh:underline and $charPr/hh:underline/@type != 'NONE'">text-decoration:
        underline; </xsl:if>
            <!-- 글자 크기 -->
            <xsl:if test="$charPr/@height">font-size: <xsl:value-of
                    select="number($charPr/@height) div 100" />pt; </xsl:if>
        </xsl:variable>

        <span
            style="{$cStyle}">
            <xsl:apply-templates />
        </span>
    </xsl:template>

    <xsl:template match="hp:t">
        <xsl:value-of select="." />
    </xsl:template>

    <xsl:template match="hp:tab">
        <span class="tab-spacer"></span>
    </xsl:template>

    <xsl:template match="hp:pic">
        <xsl:variable name="imgId" select="hc:img/@binaryItemIDRef" />
        <xsl:variable name="width"
            select="number(hp:curSz/@width) div 100" />
        <xsl:variable name="height"
            select="number(hp:curSz/@height) div 100" />
        <img
            src="{concat('file://', $base_dir, '/BinData/', $imgId, '.png')}"
            style="width: {$width}pt; height: {$height}pt;" />
    </xsl:template>

</xsl:stylesheet>